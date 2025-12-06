from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

# Initialize SQLAlchemy instance
db = SQLAlchemy()

class Product(db.Model):
    """
    Represents the metadata for a unique product type.
    This acts as a local cache of the Open Food Facts data.
    """
    __tablename__ = 'product'
    barcode = db.Column(db.String(20), primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50))
    image_url = db.Column(db.String(200))
    
    def __repr__(self):
        return f'<Product {self.name}>'

class InventoryItem(db.Model):
    """
    Represents a specific physical item in the user's pantry.
    Linked to the Product table via barcode.
    """
    __tablename__ = 'inventory_item'
    id = db.Column(db.Integer, primary_key=True)
    barcode = db.Column(db.String(20), db.ForeignKey('product.barcode'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_date = db.Column(db.DateTime, default=datetime.utcnow)
    expiration_date = db.Column(db.Date, nullable=True)
    
    # Relationship allows accessing product details (e.g., item.product.name)
    product = db.relationship('Product', backref=db.backref('items', lazy=True))

    def __repr__(self):
        return f'<InventoryItem {self.barcode} x{self.quantity}>'