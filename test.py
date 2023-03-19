import mysql.connector
import streamlit as st


def init_connection():
    conn = mysql.connector.connect(**st.secrets["db_credentials"])
    return conn


book_db = init_connection()
book_cursor = book_db.cursor()



book_cursor.execute("""SELECT metadata.title
                    FROM metadata
                    WHERE unique_id = 2""")
results = book_cursor.fetchall()



book_cursor.close()
book_db.close()












