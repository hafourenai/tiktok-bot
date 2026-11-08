# -*- coding: utf-8 -*-
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import requests
from PIL import Image, ImageDraw, ImageFont
import io
import json
import os
from datetime import datetime
from config import (
    CSV_URL, PUBLIC_DIR, CACHE_DIR, KATEGORI_MAP, KATEGORI_COLOR,
    IMAGE_CONFIG, MENU_IMAGE, MENU_CACHE
)

# Ensure directories exist
os.makedirs(PUBLIC_DIR, exist_ok=True)
os.makedirs(CACHE_DIR, exist_ok=True)

def fetch_csv_data():
    """Fetch data dari Google Sheets CSV"""
    try:
        df = pd.read_csv(CSV_URL)
        print(f"[OK] Data fetched. Total items: {len(df)}")
        return df
    except Exception as e:
        print(f"[ERROR] Error fetching CSV: {e}")
        return None

def filter_menu_items(df):
    """Filter items: stok > 0 dan aktif = TRUE"""
    # Convert stok to numeric, handle any issues
    df['stok'] = pd.to_numeric(df['stok'], errors='coerce')
    df['aktif'] = df['aktif'].astype(str).str.upper()
    
    # Filter
    filtered = df[(df['stok'] > 0) & (df['aktif'] == 'TRUE')].copy()
    print(f"[OK] Filtered items (stok > 0 & aktif = TRUE): {len(filtered)}")
    return filtered

def get_kategori(kode):
    """Get kategori berdasarkan prefix kode"""
    for prefix, kategori in KATEGORI_MAP.items():
        if kode.startswith(prefix):
            return kategori
    return "Lainnya"

def group_by_kategori(df):
    """Group items by kategori"""
    df['kategori'] = df['kode'].apply(get_kategori)
    grouped = df.groupby('kategori')
    
    # Sort by order yang ada di KATEGORI_MAP
    kategori_order = list(KATEGORI_MAP.values())
    grouped_dict = {}
    for kat in kategori_order:
        if kat in grouped.groups:
            grouped_dict[kat] = grouped.get_group(kat).reset_index(drop=True)
    
    return grouped_dict

def format_price(price):
    """Format harga ke Rupiah"""
    try:
        return f"Rp {int(price):,}".replace(",", ".")
    except:
        return "Rp 0"

def generate_menu_image(grouped_items):
    """Generate gambar menu menggunakan PIL untuk hasil yang lebih baik"""
    
    # Calculate dimensions
    total_items = sum(len(items) for items in grouped_items.values())
    total_categories = len(grouped_items)
    
    # Image dimensions (width x height in pixels)
    img_width = 1200
    img_height = 200 + (total_items * 40) + (total_categories * 50)
    
    # Create image with background
    img = Image.new('RGB', (img_width, img_height), color='#F8F9FA')
    draw = ImageDraw.Draw(img)
    
    try:
        title_font = ImageFont.truetype("arial.ttf", 48)
        category_font = ImageFont.truetype("arial.ttf", 24)
        item_font = ImageFont.truetype("arial.ttf", 20)
        price_font = ImageFont.truetype("arial.ttf", 18)
    except:
        # Fallback ke default font
        title_font = ImageFont.load_default()
        category_font = ImageFont.load_default()
        item_font = ImageFont.load_default()
        price_font = ImageFont.load_default()
    
    y_position = 30
    
    # Header
    draw.rectangle([(0, 0), (img_width, 100)], fill='#2C3E50')
    header_text = "🍽️ MENU TERSEDIA 🍽️"
    bbox = draw.textbbox((0, 0), header_text, font=title_font)
    text_width = bbox[2] - bbox[0]
    x_center = (img_width - text_width) // 2
    draw.text((x_center, 25), header_text, fill='#FFFFFF', font=title_font)
    
    y_position = 120
    
    # Iterate through categories
    for kategori, items in grouped_items.items():
        # Category header
        color = KATEGORI_COLOR.get(kategori, "#999999")
        # Convert hex to RGB
        hex_color = color.lstrip('#')
        rgb_color = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        
        draw.rectangle([(20, y_position), (img_width - 20, y_position + 40)], fill=rgb_color)
        draw.text((40, y_position + 8), kategori, fill='#FFFFFF', font=category_font)
        y_position += 50
        
        # Items in category
        for idx, (_, item) in enumerate(items.iterrows()):
            nama = item['nama']
            harga = format_price(item['harga'])
            
            # Alternating row colors
            if idx % 2 == 0:
                draw.rectangle([(20, y_position), (img_width - 20, y_position + 38)], fill='#FFFFFF')
            else:
                draw.rectangle([(20, y_position), (img_width - 20, y_position + 38)], fill='#F0F0F0')
            
            # Item name
            draw.text((50, y_position + 6), nama, fill='#2C3E50', font=item_font)
            
            # Price
            draw.text((img_width - 250, y_position + 6), harga, fill='#27AE60', font=price_font)
            
            # Status badge
            draw.text((img_width - 120, y_position + 6), "✓ Tersedia", fill='#27AE60', font=price_font)
            
            y_position += 40
        
        y_position += 10
    
    # Footer
    footer_text = f"Update: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    draw.text((40, y_position + 20), footer_text, fill='#7F8C8D', font=price_font)
    
    # Save image
    output_path = os.path.join(PUBLIC_DIR, MENU_IMAGE)
    img.save(output_path, quality=95)
    print(f"[OK] Menu image saved: {output_path}")
    
    return output_path

def get_data_hash(df):
    """Create hash dari data untuk detect perubahan"""
    return hash(pd.util.hash_pandas_object(df).values.tobytes())

def load_cache():
    """Load cache data"""
    cache_path = os.path.join(CACHE_DIR, MENU_CACHE)
    if os.path.exists(cache_path):
        with open(cache_path, 'r') as f:
            return json.load(f)
    return None

def save_cache(df):
    """Save cache data"""
    cache_path = os.path.join(CACHE_DIR, MENU_CACHE)
    cache_data = {
        'hash': str(get_data_hash(df)),
        'timestamp': datetime.now().isoformat(),
        'count': len(df)
    }
    with open(cache_path, 'w') as f:
        json.dump(cache_data, f)

def has_stok_changes(df):
    """Check apakah ada perubahan stok dibanding cache"""
    current_hash = str(get_data_hash(df))
    cache = load_cache()
    
    if cache is None:
        return True  # First time, always regenerate
    
    if current_hash != cache.get('hash'):
        print(f"[OK] Stok changes detected!")
        return True
    
    return False

def main():
    """Main function untuk generate menu"""
    print("\n" + "="*50)
    print("[*] Starting menu generation...")
    print("="*50)
    
    # Fetch data
    df = fetch_csv_data()
    if df is None:
        print("[X] Failed to fetch data. Exiting.")
        return False
    
    # Filter
    filtered_df = filter_menu_items(df)
    if len(filtered_df) == 0:
        print("[X] No items available. Exiting.")
        return False
    
    # Check changes
    if not has_stok_changes(filtered_df):
        print("[i] No changes detected. Skipping image regeneration.")
        return False
    
    # Group by kategori
    grouped = group_by_kategori(filtered_df)
    
    # Generate image
    generate_menu_image(grouped)
    
    # Save cache
    save_cache(filtered_df)
    
    print("[OK] Menu generation completed successfully!")
    print("="*50 + "\n")
    
    return True

if __name__ == "__main__":
    main()
