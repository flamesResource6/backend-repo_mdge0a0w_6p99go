import os
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional

from database import db, create_document, get_documents

app = FastAPI(title="Live Sports Auction API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateAuctionRequest(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    starting_price: float
    start_time: datetime
    end_time: datetime
    tags: List[str] = []


class PlaceBidRequest(BaseModel):
    bidder_name: str
    amount: float


@app.get("/")
def read_root():
    return {"message": "Live Sports Auction API is running"}


@app.get("/auctions")
def list_auctions(status: Optional[str] = None, limit: int = 20):
    """List auctions, optionally by status"""
    filter_dict = {}
    if status:
        filter_dict["status"] = status
    auctions = get_documents("auction", filter_dict, limit)
    # Convert ObjectId to string and compute time-related flags
    for a in auctions:
        a["id"] = str(a.pop("_id"))
        now = datetime.now(timezone.utc)
        a["is_live"] = a.get("start_time") <= now <= a.get("end_time")
        a["has_ended"] = now > a.get("end_time")
    return auctions


@app.post("/auctions")
def create_auction(payload: CreateAuctionRequest):
    """Create a new auction"""
    from schemas import Auction as AuctionSchema

    status = "scheduled"
    now = datetime.now(timezone.utc)
    if payload.start_time <= now <= payload.end_time:
        status = "live"
    elif now > payload.end_time:
        status = "ended"

    data = AuctionSchema(
        item_id=None,
        title=payload.title,
        description=payload.description,
        image_url=payload.image_url,
        starting_price=payload.starting_price,
        current_price=payload.starting_price,
        start_time=payload.start_time,
        end_time=payload.end_time,
        status=status,
        tags=payload.tags,
    )

    inserted_id = create_document("auction", data)
    return {"id": inserted_id}


@app.get("/auctions/{auction_id}")
def get_auction(auction_id: str):
    from bson import ObjectId

    try:
        doc = db["auction"].find_one({"_id": ObjectId(auction_id)})
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid auction id")

    if not doc:
        raise HTTPException(status_code=404, detail="Auction not found")

    doc["id"] = str(doc.pop("_id"))

    # gather top bids
    bids = list(db["bid"].find({"auction_id": auction_id}).sort("amount", -1).limit(10))
    for b in bids:
        b["id"] = str(b.pop("_id"))
    doc["top_bids"] = bids
    return doc


@app.post("/auctions/{auction_id}/bids")
def place_bid(auction_id: str, payload: PlaceBidRequest):
    """Place a bid if auction is live and bid is higher than current"""
    from bson import ObjectId

    auction = db["auction"].find_one({"_id": ObjectId(auction_id)})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    now = datetime.now(timezone.utc)
    if not (auction["start_time"] <= now <= auction["end_time"]):
        raise HTTPException(status_code=400, detail="Auction is not live")

    current_price = float(auction.get("current_price", auction.get("starting_price", 0)))
    if payload.amount <= current_price:
        raise HTTPException(status_code=400, detail="Bid must be higher than current price")

    # insert bid
    bid_doc = {
        "auction_id": auction_id,
        "bidder_name": payload.bidder_name,
        "amount": float(payload.amount),
        "created_at": now,
    }
    inserted_id = db["bid"].insert_one(bid_doc).inserted_id

    # update auction current price and updated_at
    db["auction"].update_one({"_id": ObjectId(auction_id)}, {"$set": {"current_price": float(payload.amount), "updated_at": now}})

    return {"id": str(inserted_id), "current_price": float(payload.amount)}


@app.get("/schema")
def get_schema_info():
    """Expose schema classes for tooling."""
    from schemas import SportsItem, Bid, Auction
    return {
        "sportsitem": SportsItem.model_json_schema(),
        "bid": Bid.model_json_schema(),
        "auction": Auction.model_json_schema(),
    }


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
