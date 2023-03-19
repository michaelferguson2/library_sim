import pandas as pd
import mysql.connector
import streamlit as st
import time

st.set_page_config(page_title="Library Simulation",
                   page_icon=r"./data/closed_book.png",
                   layout="wide")


st.sidebar.markdown("""
        <style>
               .block-container {
                    padding-top: 1rem;
                    padding-bottom: 1rem;
                    padding-left: 1rem;
                    padding-right: 1rem;
                }
        </style>
        """, unsafe_allow_html=True)


@st.cache_resource
def init_connection():
    conn = mysql.connector.connect(**st.secrets["db_credentials"])
    return conn


book_db = init_connection()
book_cursor = book_db.cursor()

if 'active_user' not in st.session_state:
    st.session_state['active_user'] = 'no_user'

active_user = st.session_state['active_user']


@st.cache_data(ttl=600)
def search_books(term, kind):

    def search_books_by_author(author):
        book_cursor.execute(f"""SELECT inventory.book_id, metadata.title, 
                           metadata.author, inventory.total_copies, 
                           inventory.available,metadata.desc, 
                           metadata.cover_link
                           FROM inventory
                           LEFT JOIN metadata
                           ON inventory.book_id = metadata.unique_id
                           WHERE metadata.author LIKE '%{author}%';""")
        results = book_cursor.fetchall()
        return [results[0:][x] for x in range(len(results))]

    def search_books_by_title(title):
        book_cursor.execute(f"""SELECT inventory.book_id, metadata.title, 
                           metadata.author, inventory.total_copies, 
                           inventory.available,metadata.desc, 
                           metadata.cover_link
                           FROM inventory
                           LEFT JOIN metadata
                           ON inventory.book_id = metadata.unique_id
                           WHERE metadata.title LIKE '%{title}%';""")
        results = book_cursor.fetchall()
        return [results[0:][x] for x in range(len(results))]

    if "title" == kind:
        return search_books_by_title(term)
    else:
        return search_books_by_author(term)


def create_user(new_user_name, new_user_pass):
    try:
        book_cursor.execute(f"""INSERT INTO users (user_name, user_pass)
                           VALUES ('{new_user_name}', 
                           SHA2('{new_user_pass}',256));""")
        book_db.commit()
        print("New User Added to Database")
        return True
    except mysql.connector.Error as err:
        print("{}".format(err))
        return False   


def login_user(user_name, user_pass):

    book_cursor.execute(f"""SELECT user_name FROM users
                       WHERE user_name ='{user_name}' 
                       AND user_pass = SHA2('{user_pass}', 256)""")
                   
    results = book_cursor.fetchall()
    if user_name == results[0][0]:
        print('login success')
        return results
    else:
        print('failure')
        return results


def html_image(image_link):
    return f"<img align='right' width='130' height='200' src='{image_link}'>"


def user_book_checkout(user_id, book_id):

    def check_available(value):
        try:
            book_cursor.execute(f"""SELECT  inventory.total_copies, 
                                    inventory.available
                                    FROM inventory
                                    WHERE inventory.book_id ={value};""")
            check_avail = book_cursor.fetchall()

            if check_avail[0][1] >= 0:
                return True
            else:
                return False
        except mysql.connector.Error as err:
            print("{}".format(err))
            return False

    def check_out_inventory(value):
        book_cursor.execute(f"""SELECT  inventory.total_copies, 
                            inventory.available
                            FROM inventory
                            WHERE inventory.book_id ={value};""")
        results = book_cursor.fetchall()
        update_value = results[0][1] - 1
        book_cursor.execute(f"""UPDATE inventory
                           SET available = {update_value}
                           WHERE book_id = {value};""")

    def insert_to_circulation(user, value):

        book_cursor.execute(f"""INSERT INTO circulation (user_id, book_id)
                           VALUES ('{user}', {value});""")

    if not check_available(book_id):
        return False
    else:
        check_out_inventory(book_id)
        insert_to_circulation(user_id, book_id)
        book_db.commit()
        return True


# sidebar login/signup layout
if 'no_user' == active_user:
    choice = st.sidebar.selectbox('#', ['Login', 'Signup'],
                                  label_visibility='collapsed')

    if choice == 'Login':
    
        login_user_name = st.sidebar.text_input("Username")
        login_user_pass = st.sidebar.text_input("Password", type="password")

        if st.sidebar.button("Login"):
            result = login_user(login_user_name, login_user_pass)
            if 0 < len(result):
                st.sidebar.success("Successful Login")
                st.session_state["active_user"] = result[0][0]
                time.sleep(2)
                st.experimental_rerun()
            else:
                st.sidebar.warning("Incorrect Username/Password")

    elif choice == "Signup":

        signup_user_name = st.sidebar.text_input('Username')
        signup_user_pass = st.sidebar.text_input('Password', type='password')

        if st.sidebar.button('Signup'):
            result = create_user(signup_user_name, signup_user_pass)
            if result:
                st.sidebar.success('New User Created')
                time.sleep(2)
                st.experimental_rerun()
                init_connection.clear()
            else:
                st.sidebar.warning('Username Already Exists')
else:
    if st.sidebar.button('Logout'):
        st.session_state['active_user'] = 'no_user'
        st.sidebar.success('Successfully Logged Out')
        time.sleep(2)
        st.experimental_rerun()

    st.sidebar.subheader(f'Hello *{active_user}*!')
    st.sidebar.markdown("Input a Book ID to add to 'My Books'")
    check_out_id = st.sidebar.text_input('#', label_visibility="collapsed")

    if st.sidebar.button('Add to My Books'):
        result = user_book_checkout(active_user, check_out_id)
        if not result:
            st.sidebar.warning('Book Not Found or Not Available')
        else:
            st.sidebar.success('Success!')


# main page layout
st.title('Simple Library Simulation', anchor=None)
library_sim_explanation = """This is simple library simulation allows users 
can create accounts, search for different titles or authors, and 
check-out/return books."""
st.markdown(library_sim_explanation)

search_type = st.radio('Search Type', ('title', 'author'), horizontal=True)
search_term = st.text_input('#', placeholder="search",
                            label_visibility="collapsed")

display_df = pd.DataFrame(search_books(search_term, search_type),
                          columns=['Book ID', 'Title', 'Author', 'Total Copies',
                                   'Available', 'Description', 'Cover'])
display_df = display_df.iloc[:5]
display_df = display_df[['Book ID', 'Cover', 'Title', 'Author',
                         'Description', 'Available']]

display_df['Description'] = display_df['Description'].str.replace("###",
                                                                  "<br />",
                                                                  regex=False)
display_df['Description'] = display_df['Description'].str.replace("#",
                                                                  "",
                                                                  regex=False)

display_df['Cover'] = display_df['Cover'].apply(html_image)
book_display_html = display_df.to_html(escape=False, index=False,
                                       justify='center')
st.markdown(book_display_html, unsafe_allow_html=True)


# book_cursor.close()
# book_db.close()
# streamlit run 1_🏠_Home.py
