"""
Database Schemas for Live Sports Auction App

Each Pydantic model represents a MongoDB collection. The collection name is the
lowercased class name by convention (e.g., Auction -> "auction").
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class SportsItem(BaseModel):
    """Sports memorabilia or experience being auctioned"""
    title: str = Field(..., description="Item title, e.g., 'Signed Jersey'"
    )
    description: Optional[str] = Field(None, description="Details about the item")
    sport: Optional[str] = Field(None, description="Sport type, e.g., Football")
    team: Optional[str] = Field(None, description="Associated team")
    player: Optional[str] = Field(None, description="Associated player")
    image_url: Optional[str] = Field(None, description="Primary image URL")

class Bid(BaseModel):
    """A bid placed on an auction"""
    auction_id: str = Field(..., description="Auction ID")
    bidder_name: str = Field(..., description="Display name for bidder")
    amount: float = Field(..., gt=0, description="Bid amount")

class Auction(BaseModel):
    """Auction metadata"""
    item_id: Optional[str] = Field(None, description="Reference to a SportsItem")
    title: str = Field(..., description="Auction title")
    description: Optional[str] = Field(None, description="Auction description")
    image_url: Optional[str] = Field(None, description="Hero image for auction")
    starting_price: float = Field(..., ge=0, description="Starting price")
    current_price: Optional[float] = Field(None, ge=0, description="Cached current price")
    start_time: datetime = Field(..., description="When the auction starts")
    end_time: datetime = Field(..., description="When the auction ends")
    status: str = Field("scheduled", description="scheduled | live | ended")
    tags: List[str] = Field(default_factory=list, description="Searchable tags")
