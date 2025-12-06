from flask import Flask, render_template, request, redirect, url_for, flash
from models import db, Product, InventoryItem
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
# Database Configuration
app.config = 'sqlite:///skiss.db'
app.config = False
app.config = 'skiss-dev-secret-key'

db.init_app(app)

SPOONACULAR_KEY = os.getenv('SPOONACULAR_API_KEY')

@app.route('/')
def index():
    """
    Home Dashboard. Displays the current inventory list.
    """
    items = InventoryItem.query.all()
    return render_template('index.html', items=items)

@app.route('/delete/<int:id>')
def delete_item(id):
    """
    Removes an item from inventory (Usage scenario).
    """
    item = InventoryItem.query.get_or_404(id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/recipes')
def recipes():
    """
    Queries Spoonacular API to find recipes based on current inventory.
    """
    items = InventoryItem.query.all()
    if not items:
        return render_template('recipes.html', recipes=[], error="Pantry is empty!")
    
    # Create comma-separated list of ingredients
    ingredients = ','.join([item.product.name for item in items])
    
    url = "https://api.spoonacular.com/recipes/findByIngredients"
    params = {
        'apiKey': SPOONACULAR_KEY,
        'ingredients': ingredients,
        'number': 5, # Limit to 5 recipes to save API quota
        'ranking': 1 # Maximize used ingredients
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            return render_template('recipes.html', recipes=data)
        else:
            return render_template('recipes.html', recipes=[], error="API Limit Reached or Error")
    except Exception as e:
        return render_template('recipes.html', recipes=[], error=str(e))

if __name__ == '__main__':
    # Create database tables if they don't exist
    with app.app_context():
        db.create_all()
    # Run on 0.0.0.0 to be accessible across the LAN
    app.run(host='0.0.0.0', port=5000, debug=False)