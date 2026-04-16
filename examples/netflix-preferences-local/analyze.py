#!/usr/bin/env python3
"""
Netflix Customer Preferences Analytics
Demonstrates querying and analyzing customer viewing data using pandas.
"""
import pandas as pd
from pathlib import Path

def main():
    print("=" * 80)
    print("📺 NETFLIX CUSTOMER PREFERENCES ANALYTICS")
    print("=" * 80)
    
    # Load data
    customers = pd.read_csv('data/customers.csv')
    viewing = pd.read_csv('data/viewing_history.csv')
    
    # Convert dates
    customers['signup_date'] = pd.to_datetime(customers['signup_date'])
    viewing['watch_date'] = pd.to_datetime(viewing['watch_date'])
    
    # 1. Customer Overview
    print("\n👥 Customer Overview:")
    print("-" * 80)
    print(f"Total Customers: {len(customers)}")
    print(f"Total Views: {len(viewing)}")
    print(f"\nSubscription Distribution:")
    print(customers['subscription_tier'].value_counts().to_string())
    print(f"\nCountry Distribution:")
    print(customers['country'].value_counts().to_string())
    
    # 2. Genre Preferences
    print("\n\n🎬 Genre Preferences by Customer:")
    print("-" * 80)
    
    genre_prefs = viewing.merge(
        customers[['customer_id', 'name']], 
        on='customer_id'
    ).groupby(['customer_id', 'name', 'genre']).agg({
        'view_id': 'count',
        'watch_duration_minutes': 'sum',
        'completion_percent': 'mean',
        'rating': 'mean'
    }).rename(columns={
        'view_id': 'total_views',
        'watch_duration_minutes': 'total_minutes',
        'completion_percent': 'avg_completion',
        'rating': 'avg_rating'
    }).reset_index()
    
    # Save genre preferences
    Path('output').mkdir(exist_ok=True)
    genre_prefs.to_csv('output/genre_preferences.csv', index=False)
    print(genre_prefs.head(10).to_string(index=False))
    
    # 3. Top Genres Overall
    print("\n\n⭐ Top Genres Overall:")
    print("-" * 80)
    top_genres = viewing.groupby('genre').agg({
        'view_id': 'count',
        'watch_duration_minutes': 'sum',
        'completion_percent': 'mean',
        'rating': 'mean'
    }).rename(columns={
        'view_id': 'total_views',
        'watch_duration_minutes': 'total_minutes',
        'completion_percent': 'avg_completion',
        'rating': 'avg_rating'
    }).round(2).sort_values('total_views', ascending=False)
    print(top_genres.to_string())
    
    # 4. Customer Engagement Summary
    print("\n\n📊 Customer Engagement Summary:")
    print("-" * 80)
    
    customer_stats = viewing.groupby('customer_id').agg({
        'view_id': 'count',
        'watch_duration_minutes': 'sum',
        'completion_percent': 'mean',
        'genre': lambda x: x.value_counts().index[0]  # most common genre
    }).rename(columns={
        'view_id': 'total_views',
        'watch_duration_minutes': 'total_minutes',
        'completion_percent': 'avg_completion_rate',
        'genre': 'favorite_genre'
    })
    
    # Add customer info
    engagement = customers.merge(customer_stats, on='customer_id')
    engagement['total_watch_hours'] = (engagement['total_minutes'] / 60).round(2)
    
    # Calculate engagement score (0-100)
    # Based on: views (40%), watch hours (30%), completion rate (30%)
    max_views = engagement['total_views'].max()
    max_hours = engagement['total_watch_hours'].max()
    
    engagement['engagement_score'] = (
        (engagement['total_views'] / max_views * 40) +
        (engagement['total_watch_hours'] / max_hours * 30) +
        (engagement['avg_completion_rate'] / 100 * 30)
    ).round(2)
    
    # Select and save
    engagement_summary = engagement[[
        'customer_id', 'name', 'subscription_tier', 'total_views',
        'total_watch_hours', 'avg_completion_rate', 'favorite_genre', 'engagement_score'
    ]].rename(columns={'name': 'customer_name'})
    
    engagement_summary.to_csv('output/engagement_summary.csv', index=False)
    print(engagement_summary.sort_values('engagement_score', ascending=False).to_string(index=False))
    
    # 5. Content Performance
    print("\n\n🎥 Top Performing Content:")
    print("-" * 80)
    content_perf = viewing.groupby(['content_title', 'content_type', 'genre']).agg({
        'view_id': 'count',
        'completion_percent': 'mean',
        'rating': 'mean'
    }).rename(columns={
        'view_id': 'views',
        'completion_percent': 'avg_completion',
        'rating': 'avg_rating'
    }).round(2).sort_values('views', ascending=False)
    print(content_perf.to_string())
    
    # 6. Subscription Tier Analysis
    print("\n\n💎 Engagement by Subscription Tier:")
    print("-" * 80)
    tier_analysis = engagement.groupby('subscription_tier').agg({
        'customer_id': 'count',
        'total_views': 'mean',
        'total_watch_hours': 'mean',
        'avg_completion_rate': 'mean',
        'engagement_score': 'mean'
    }).rename(columns={
        'customer_id': 'customers'
    }).round(2)
    print(tier_analysis.to_string())
    
    print("\n" + "=" * 80)
    print("✅ Analysis complete! Output files saved to ./output/")
    print("=" * 80 + "\n")

if __name__ == "__main__":
    main()
