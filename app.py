import streamlit as st
import pandas as pd

# Load data from csv
users_df = pd.read_csv("data/users.csv")
quotes_df = pd.read_csv("data/quotes.csv")
orders_df = pd.read_csv("data/orders.csv")
materials_df = pd.read_csv("data/materials.csv")

# Calculate churned users
churn_cutoff = pd.to_datetime("today") - pd.DateOffset(days=30)
churned_users = users_df[users_df["last_login_at"] < churn_cutoff]
num_churned_users = len(churned_users)

# Calculate active users
active_users = users_df[users_df["last_login_at"] >= churn_cutoff]
num_active_users = len(active_users)

# Calculate average order value
average_order_value = orders_df["length_mm"].mean()

# Identify most active users
most_active_users = orders_df["user_id"].value_counts().head(5)

# Print the results
print("Number of churned users:", num_churned_users)
print("Number of active users:", num_active_users)
print("Average order value:", average_order_value)
print("Most active users:\n", most_active_users)
