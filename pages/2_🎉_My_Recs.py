import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import mysql.connector
import streamlit as st

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
active_user = st.session_state['active_user']


@st.cache_data
def get_metadata():
    book_cursor.execute("""SELECT metadata.title, metadata.desc,
                        metadata.author, metadata.genre, metadata.unique_id, 
                        metadata.cover_link
                        FROM metadata;""")
    results = book_cursor.fetchall()
    return results


query_results = get_metadata()
query_table = pd.DataFrame(query_results,
                           columns=['title', 'desc', 'author', 'genre',
                                    'unique_id', 'cover_link'])
indices = pd.Series(query_table.index, index=query_table['unique_id'])

query_table['genre'] = query_table['genre'].str.replace("'", "", regex=False)
query_table['genre'] = query_table['genre'].str.replace(", ", ",", regex=True)
query_table['genre'] = query_table.genre.apply(lambda x: x[1:-1].split(','))


# noinspection SpellCheckingInspection
@st.cache_data
def desc_sim_matrix():
    tfid = TfidfVectorizer(stop_words='english')
    desc_matrix = tfid.fit_transform(query_table['desc'].astype(str))
    similarity = cosine_similarity(desc_matrix, desc_matrix)
    return similarity


def desc_sim(book_id, sim_matrix):
    idx = indices[book_id]
    sim_scores = list(enumerate(sim_matrix[idx]))
    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
    sim_scores = sim_scores[0:20]
    book_indices = [i[0] for i in sim_scores]
    frame = {'query_table_index': book_indices,
             'title': query_table['title'].iloc[book_indices],
             'unique_id': query_table['unique_id'].iloc[book_indices]}
    dataframe = pd.DataFrame(frame)
    return dataframe


desc_similarity = desc_sim_matrix()


def rec_table(eng_output):
    """Takes engine output and creates full dataframe"""
    output_index = eng_output['query_table_index']
    frame = {
        'title': [query_table['title'][i] for i in output_index],
        'author': [query_table['author'][i] for i in output_index],
        'desc': [query_table['desc'][i] for i in output_index],
        'genre': [query_table['genre'][i] for i in output_index],
        'cover_link': [query_table['cover_link'][i] for i in output_index],
        'unique_id': [query_table['unique_id'][i] for i in output_index],
        'query_table_index': output_index
    }
    dataframe = pd.DataFrame(frame)
    return dataframe


def html_image(image_link):
    return f"<img align='right' width='130' height='200' src='{image_link}'>"


def overlap_by_genre(user_select, table, num_overlap):
    def list_overlap(a, b, num_):
        if len(set(a) & set(b)) > num_:
            return True
        else:
            return False

    indexes = []
    titles = []
    unique_ids = []
    for i in range(len(table['query_table_index'])):
        if list_overlap(user_select['genre'],
                        table['genre'].iloc[i], num_overlap) is True:
            indexes.append(table['query_table_index'].iloc[i])
            titles.append(table['title'].iloc[i])
            unique_ids.append(table['unique_id'].iloc[i])

    dataframe = pd.DataFrame({'query_table_index': indexes,
                              'title': titles,
                              'unique_id': unique_ids})
    return dataframe


def limit_by_genre(table, genre=None):
    table.reset_index(inplace=True, drop=True)

    if type(genre) == str:
        genre = [genre]  # this is because of how streamlit works

    keep = []
    if genre is None:
        return table
    elif len(genre) == 1 and genre[0] != 'All':
        for i in range(len(table['genre'])):
            if genre[0] in table['genre'][i]:
                keep.append(i)
        return table.iloc[keep]
    else:
        for i in range(len(table['title'])):
            if len(set(genre) & set(table['genre'][i])) == len(set(genre)):
                keep.append(i)
        return table.iloc[keep]


def include_author(suggestion, table, include=True):
    if include is False:
        table = table.loc[table['author'] != suggestion['author']]
    return table


def book_rec(user_selection, matrix, book_id,
             genres=None, overlap=0, author=False):

    full_recs = desc_sim(user_selection[book_id], matrix)
    rec_output = rec_table(full_recs)

    if genres is not None:
        limit_output = limit_by_genre(rec_output, genre=genres)
        rec_output = rec_table(limit_output)

    if overlap != 0:
        overlap_output = overlap_by_genre(user_selection, rec_output, overlap)
        rec_output = rec_table(overlap_output)

    rec_output = include_author(user_selection, rec_output, author)

    return rec_output


def book_recs_multiple(author_titles, book_id, genres=None, num_=5):
    dfs_list = []
    for val in range(len(author_titles[book_id])):
        dfs_list.append(book_rec(author_titles.iloc[val], desc_similarity,
                                 book_id, genres=genres, overlap=5,
                                 author=False).iloc[0:num_])

    df = pd.concat(dfs_list, ignore_index=True)
    df.drop_duplicates(subset=['unique_id'], inplace=True)

    if len(df['desc']) != 0:
        return df
    else:
        cover = """https://upload.wikimedia.org/wikipedia/commons/4/4d/
        Cat_November_2010-1a.jpg"""
        df = pd.DataFrame({'Book ID': 'NA', 'Cover': cover, 'Title': 'NA',
                           'Author': 'NA', 'Description': 'NA',
                           'Genres': ['NA']},
                          index=[0])
        return df


st.title('Simple Library Simulation', anchor=None)
st.subheader("Recommendations based on current \"My Books\" selection")

my_books = st.session_state['active_my_books']

if "no_user" == active_user:
    logged_out_text = """Please Login on the Home page to see your currently 
    books"""
    st.sidebar.markdown(logged_out_text)
elif my_books is None:
    load_my_books_text = """Please load the "My Books" page to generate your 
    recommendations"""
    st.sidebar.markdown(load_my_books_text)
elif my_books.empty:
    no_books_test = """It looks like you haven't added any books to you 'My 
    Books'. Add new books to get personal recommendations."""
    st.sidebar.markdown(no_books_test)
else:
    my_books_genres = []
    for ib in my_books['Book ID']:
        my_books_genres.append(query_table.loc[
                               query_table['unique_id'] == ib, 'genre'].iloc[0])

    my_books['genre'] = my_books_genres
    my_books.rename(columns={'Author': 'author'}, inplace=True)

    my_recs = book_recs_multiple(my_books, 'Book ID', genres=None, num_=1)

    # st.dataframe(my_recs)

    combo_df = pd.DataFrame({'Book ID': my_recs['unique_id'],
                             'You May Like':
                             my_recs['title']+' by '+my_recs['author'],
                             'Cover': my_recs['cover_link'],
                             'Description': my_recs['desc'],
                             'Because You Liked':
                             my_books['Title']+' by '+my_books['author']
                             })

    combo_df['Cover'] = combo_df['Cover'].apply(html_image)
    combo_df['Description'] = combo_df['Description'].str.replace("###",
                                                                  "<br />",
                                                                  regex=False)
    combo_df['Description'] = combo_df['Description'].str.replace("#", "",
                                                                  regex=False)

    combo_df = combo_df.to_html(escape=False, index=False, justify='center')

    st.markdown(combo_df, unsafe_allow_html=True)
