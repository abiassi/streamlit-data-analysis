import streamlit as st
import pandas as pd
import datetime
import matplotlib.pyplot as plt
import geopandas as gpd
from geolite2 import geolite2
import pycountry
import numpy as np


# Load data
users = pd.read_csv('data/users.csv')
materials = pd.read_csv('data/materials.csv')
orders = pd.read_csv('data/orders.csv')
quotes = pd.read_csv('data/quotes.csv')

# Convert dates to datetime
users['created_at'] = pd.to_datetime(users['created_at'])
users['deleted_at'] = pd.to_datetime(users['deleted_at'])
users['last_login_at'] = pd.to_datetime(users['last_login_at'])
orders['delivery_date'] = pd.to_datetime(orders['delivery_date'])

# Define churned users as users who deleted their account, 
# or haven't placed an order or logged in in the last 3 months
three_months_ago = datetime.datetime.now() - datetime.timedelta(days=3*30)
churned_users = users[(users['deleted_at'].notna()) | 
                  (users['last_login_at'] < three_months_ago) | 
                  (users['id'].isin(orders['user_id']) == False) | 
                  (orders[orders['user_id'].isin(users['id'])]['delivery_date'].max() < three_months_ago)]

# Calculate churn rate
churn_rate = len(churned_users) / len(users)

# Merge orders and quotes
orders_quotes = pd.merge(orders, quotes, left_on='id', right_on='order_id', suffixes=('_order', '_quote'), how='inner')

# Merge with materials
orders_quotes_materials = pd.merge(orders_quotes, materials, left_on='material_id', right_on='id', suffixes=('', '_material'), how='inner')

# Calculate order value in orders_quotes
orders_quotes_materials['order_value'] = (orders_quotes_materials['labor_hours'] * orders_quotes_materials['labor_rate']) + (orders_quotes_materials['unit_price'] * orders_quotes_materials['quantity'])

# Active users
active_users = users[~users['id'].isin(churned_users['id'])]

# Merge with active users
active_users_with_orders_values = pd.merge(active_users, orders_quotes_materials, left_on='id', right_on='user_id', suffixes=('_user', ''), how='inner')

# Calculate sum of order values and count of orders per user
user_order_summary = active_users_with_orders_values.groupby('id_user').agg({
    'order_value': ['sum', 'count']
}).reset_index()

# Flatten the columns
user_order_summary.columns = ['user_id', 'total_order_value', 'order_count']

# Group by week and count orders
orders_per_week = orders.resample('W', on='delivery_date').size()

# Group by week and count new users
new_users_per_month = users.resample('M', on='created_at').size()

# Group by material and sum quantities
material_order_count = orders.groupby('material_id')['quantity'].sum().reset_index(name='order_count')

# Merge with materials to get material names
material_order_count = material_order_count.merge(materials[['id', 'material_name']], left_on='material_id', right_on='id')

# Select top 3 materials
top_3_materials = material_order_count.nlargest(3, 'order_count')

# Exclude 'material_id' and 'id' columns
top_3_materials = top_3_materials.drop(['material_id', 'id'], axis=1)

# Group by finish and count orders
finish_order_count = orders.groupby('finish').size().reset_index(name='order_count')

# Select top 3 finishes
top_3_finishes = finish_order_count.nlargest(3, 'order_count')

# Calculate total annual revenue
annual_revenue = orders_quotes_materials[orders_quotes_materials['delivery_date'].dt.year == datetime.datetime.now().year]['order_value'].sum()

# Calculate total users
total_users = len(users)

# Merge user details with user_order_summary 
user_order_summary = user_order_summary.merge(users[['id', 'first_name', 'last_name', 'email']], left_on='user_id', right_on='id')


# Calculate ARPU
arpu = annual_revenue / total_users

# Merge users and orders on user_id
users_orders = pd.merge(users, orders, how='inner', left_on='id', right_on='user_id')

# Calculate the time from user sign-up to first delivery for each user
users_orders['signup_to_first_delivery'] = users_orders.groupby('user_id')['delivery_date'].transform('min') - users_orders['created_at']

# Convert the timedelta to days
users_orders['signup_to_first_delivery'] = users_orders['signup_to_first_delivery'].dt.days

# Remove any negative values (these could occur if there was a mistake in the data and a delivery date is before a sign-up date)
users_orders = users_orders[users_orders['signup_to_first_delivery'] >= 0]

# Drop duplicate user entries, keeping only the first entry
users_orders = users_orders.drop_duplicates(subset='user_id', keep='first')


# Now, plot the histogram as before
figSignupToFirstDelivery, ax = plt.subplots()
ax.hist(users_orders['signup_to_first_delivery'], bins=10, edgecolor='white')
ax.set_xlabel('Days')
ax.set_ylabel('Users')

# Calculate average order value
average_order_value = orders_quotes_materials['order_value'].mean()

# Plot histograms
figOrderSize, ax = plt.subplots()
n, bins, patches = ax.hist(orders_quotes_materials['order_value'], bins=10, edgecolor='white', alpha=0.5, label='Order Value')
ax.set_xlabel('Order Value')
ax.set_ylabel('Number of Orders')

# Create a new Y-axis for revenue
ax2 = ax.twinx() 

# Calculate total revenue for each bin
revenues = []
for i in range(len(bins)-1):
    # All order values within the current bin
    bin_orders = orders_quotes_materials[(orders_quotes_materials['order_value'] >= bins[i]) & (orders_quotes_materials['order_value'] < bins[i+1])]
    
    # Total revenue from the current bin
    bin_revenue = bin_orders['order_value'].sum()
    revenues.append(bin_revenue)

# The X values for the line plot are the mid-points of the bins
bin_mids = bins[:-1] + np.diff(bins) / 2

# Plot revenue on the second Y-axis
ax2.plot(bin_mids, revenues, color='red', label='Revenue')
ax2.set_ylabel('Revenue')

# Add legends
lines, labels = ax.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax2.legend(lines + lines2, labels + labels2, loc=0)

# Function to convert IP to country
def ip_to_country(ip):
    try:
        x = geolite2.reader().get(ip)
        return x['country']['iso_code']
    except:
        return None
    

# Apply the function to the 'ip_address' column
users['country'] = users['ip_address'].apply(ip_to_country)

# Group by country
country_counts = users['country'].value_counts().reset_index()
country_counts.columns = ['country', 'count']


# Function to convert 2-letter to 3-letter country codes
def convert_alpha_2_to_3(alpha_2):
    try:
        return pycountry.countries.get(alpha_2=alpha_2).alpha_3
    except AttributeError:
        return None

# Apply the function to the 'country' column
country_counts['country'] = country_counts['country'].apply(convert_alpha_2_to_3)

# Read in the world geometry
world = gpd.read_file(gpd.datasets.get_path('naturalearth_lowres'))

# Merge with the counts
world = world.merge(country_counts, left_on = 'iso_a3', right_on = 'country', how='left')

# Replace NaN values with 0
world['count'] = world['count'].fillna(0)

# Create the plot
fig, ax = plt.subplots(1, 1, figsize=(15, 10))

# Plot the world map with colors representing the user counts
world.plot(column='count', 
           ax=ax, 
           legend=True, 
           legend_kwds={'label': "User Counts by Country", 'orientation': "horizontal"}, 
           cmap='coolwarm')


# Write results to Streamlits
st.title('CUTR Data Analysis')
st.write("Total number of users:", len(users))
st.write("Number of churned users:", len(churned_users))
st.write("Churn rate:", churn_rate)
st.write("Number of active users:", len(active_users))
st.write("Total number of orders:", len(orders))
st.write("Average order value:", average_order_value)
st.write("Top 3 materials:")
st.write(top_3_materials)
st.write("Top 3 finishes:")
st.write(top_3_finishes)
st.write("Total revenue generated:", orders_quotes_materials['order_value'].sum())
st.write("Annual Average Revenue Per User (ARPU):", arpu)
st.write("Top 5 active users with highest number of orders:")
st.write(user_order_summary.nlargest(5, 'order_count')[['first_name', 'last_name', 'email', 'total_order_value', 'order_count']])
st.write("Top 5 active users with highest total order value:")
st.write(user_order_summary.nlargest(5, 'total_order_value')[['first_name', 'last_name', 'email', 'total_order_value', 'order_count']])
st.write("Orders per week:")
st.line_chart(orders_per_week)
st.write("New users per month:")
st.line_chart(new_users_per_month)
st.write("Time from Sign Up to First Delivery:")
st.pyplot(figSignupToFirstDelivery)
st.write("Order Value and Revenue Distribution:")
st.pyplot(figOrderSize)
st.write("User by country:")
st.pyplot(fig)

