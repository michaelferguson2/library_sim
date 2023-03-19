import pandas as pd
import mysql.connector
import streamlit as st

st.set_page_config(page_title="Library Simulation",
                   page_icon=r"./data/closed_book.png",
                   layout="wide")


if 'active_my_books' not in st.session_state:
    st.session_state['active_my_books'] = None


@st.cache_resource
def init_connection():
    conn = mysql.connector.connect(**st.secrets["db_credentials"])
    return conn


book_db = init_connection()
book_cursor = book_db.cursor()
active_user = st.session_state['active_user']


def return_book(user_id, book_id):
    try:
        def check_available_return(value):
            try:
                book_cursor.execute(f"""SELECT inventory.total_copies, 
                                    inventory.available
                                    FROM inventory
                                    WHERE inventory.book_id ={value};""")
                avail_check = book_cursor.fetchall()
                if avail_check[0][1] < avail_check[0][0]:
                    return True
                else:
                    return False
            except mysql.connector.Error as err:
                print("{}".format(err))
                return False

        def find_book_keys_circulation(user_value, book_value):
            try:
                book_cursor.execute(f"""SELECT * FROM circulation
                                WHERE user_id = '{user_value}'
                                AND book_id = {book_value};""")
                cir_keys = book_cursor.fetchall()
                return [cir_keys[x][0] for x in range(len(cir_keys))]
            except IndexError:
                print('index error')

        def remove_circulation(user_value, cir_key):
            try:
                book_cursor.execute(f"""DELETE FROM circulation 
                                   WHERE cir_key = {cir_key} 
                                   and user_id = '{user_value}';
                                   """)
                return True
            except mysql.connector.Error as err:
                print("{}".format(err))
                return False

        def check_in_inventory(book_value):
            try:
                book_cursor.execute(f"""SELECT  inventory.total_copies, 
                                    inventory.available
                                    FROM inventory
                                    WHERE inventory.book_id ={book_value};""")
                checkin_results = book_cursor.fetchall()
                update_value = checkin_results[0][1] + 1
                book_cursor.execute(f"""UPDATE inventory
                                   SET available = {update_value}
                                   WHERE book_id = {book_value};""")
                return True
            except mysql.connector.Error as err:
                print("{}".format(err))
                return False

        if check_available_return(book_id):
            remove_keys_list = find_book_keys_circulation(user_id, book_id)
            remove_key = remove_keys_list[0]
            remove_circulation(user_id, remove_key)
            check_in_inventory(book_id)
            book_db.commit()
            return True
        else:
            return False
    except IndexError:
        print('index error')


def html_image(image_link):
    return f"<img align='right' width='130' height='200' src='{image_link}'>"


# @st.cache_data(ttl=600)
def return_active_books(active_user_val):
    book_cursor.execute(f"""SELECT circulation.user_id, circulation.book_id, 
                       metadata.author, metadata.title, metadata.cover_link,
                       metadata.desc
                       FROM circulation
                       LEFT JOIN metadata
                       ON circulation.book_id = metadata.unique_id
                       WHERE circulation.user_id = "{active_user_val}";""")
    return book_cursor.fetchall()


# layout
st.title('Simple Library Simulation')

if "no_user" == active_user:
    logged_out_text = """Please Login on the Home page to see your currently 
    books"""
    st.sidebar.markdown(logged_out_text)
else:
    my_books = pd.DataFrame(return_active_books(active_user),
                            columns=['user_id', 'Book ID', 'Author',
                                     'Title', 'Cover', 'Description'])
    my_books = my_books[['Book ID', 'Cover', 'Title',
                         'Author', 'Description']]

    my_books['Cover'] = my_books['Cover'].apply(html_image)

    my_books['Description'] = my_books['Description'].str.replace("###",
                                                                  "<br />",
                                                                  regex=False)
    my_books['Description'] = my_books['Description'].str.replace("#", "",
                                                                  regex=False)

    st.session_state['active_my_books'] = my_books

    my_books_html = my_books.to_html(escape=False, index=False,
                                     justify='center')

    st.markdown(my_books_html, unsafe_allow_html=True)

    st.sidebar.subheader(f'Hello *{active_user}*!')
    st.sidebar.markdown("Input a Book ID to Return a book")

    check_out_id = st.sidebar.text_input('#', label_visibility="collapsed")
    if st.sidebar.button('Return Book'):
        result = return_book(active_user, check_out_id)
        if result:
            st.sidebar.success('Successfully Returned!')
        else:
            st.sidebar.warning('Book Not Found In Your Library')
