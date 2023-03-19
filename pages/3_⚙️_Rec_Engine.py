import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import mysql.connector
import streamlit as st

st.set_page_config(page_title="Library Simulation",
                   page_icon=r"./data/closed_book.png",
                   layout="wide")


@st.cache_resource
def init_connection():
    conn = mysql.connector.connect(**st.secrets["db_credentials"])
    return conn


book_db = init_connection()
book_cursor = book_db.cursor()


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


def user_input_suggestion(book_id):
    result = query_table.loc[query_table['unique_id'] == book_id].iloc[0]
    return result


def search_books(term, kind):
    def search_books_by_author(author):
        book_cursor.execute(f"""SELECT inventory.book_id, metadata.title, 
                           metadata.author, inventory.total_copies, 
                           inventory.available,metadata.desc, 
                           metadata.cover_link
                           FROM inventory
                           LEFT JOIN metadata
                           ON inventory.book_id = metadata.unique_id
                           WHERE metadata.author = '{author}';""")
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
                           WHERE metadata.title = '{title}';""")
        results = book_cursor.fetchall()
        return [results[0:][x] for x in range(len(results))]

    if "title" == kind:
        return search_books_by_title(term)
    else:
        return search_books_by_author(term)


def unique_author_title(kind):
    if kind == 'author':
        book_cursor.execute(f"""SELECT distinct metadata.author
                            FROM booksdb.metadata;""")
        author_results = book_cursor.fetchall()
        return author_results
    else:
        book_cursor.execute(f"""SELECT distinct metadata.title
                        FROM booksdb.metadata;""")
        title_results = book_cursor.fetchall()
        return title_results


def book_id_title(title):
    book_cursor.execute(f"""SELECT metadata.unique_id
                        FROM booksdb.metadata
                        WHERE metadata.title = '{title}';""")
    results = book_cursor.fetchall()
    return results[0][0]


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


def list_to_text(items, sep=', '):
    def unique(sequence):
        seen = set()
        return [x for x in sequence if not (x in seen or seen.add(x))]
    items = unique(items)
    return sep.join(items)


def html_image(image_link):
    return f"<img align='right' width='130' height='200' src='{image_link}'>"


def titles_by_author(author):
    return query_table[query_table['author'] == author]


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


desc_similarity = desc_sim_matrix()

author_list = unique_author_title('author')
author_list = [item for sublist in author_list for item in sublist]
title_list = unique_author_title('title')
title_list = [item for sublist in title_list for item in sublist]


# main page layout
st.title('Simple Library Simulation', anchor=None)
st.subheader('Search for book recommendations')


# sidebar layout
search_type = st.sidebar.radio('Search Type', ('title', 'author'),
                               horizontal=True)
if 'author' == search_type:
    search_term = st.sidebar.selectbox('#', author_list, index=3,
                                       label_visibility="collapsed")

    st.sidebar.markdown("---")
    genre_list = ['Adventure', 'Childrens', 'Classics', 'Dystopia', 'Fantasy',
                  'Historical', 'Horror', 'Mystery', 'Paranormal', 'Romance',
                  'Science Fiction', 'Thriller', 'Young Adult']
    limit_genre = st.sidebar.multiselect('Only Include Below Genres?',
                                         genre_list, default=None)

    author_book_titles = list(titles_by_author(search_term)['title'])
    author_book_titles = list_to_text(author_book_titles)
    st.sidebar.markdown(f"""**{search_term}** has the following titles in the 
                        library: {author_book_titles}""")

    author_df = titles_by_author(search_term)
    recs_df = book_recs_multiple(author_df, 'unique_id', genres=limit_genre)
else:
    search_term = st.sidebar.selectbox('#', title_list, index=20,
                                       label_visibility="collapsed")
    user_val = user_input_suggestion(book_id_title(search_term))

    st.sidebar.markdown("---")
    user_val_author = user_val['author']
    author_check_text = f"""Include *{user_val_author}* in recommendations?"""
    author_check = st.sidebar.checkbox(author_check_text, value=False)

    genre_list = ['Adventure', 'Childrens', 'Classics', 'Dystopia', 'Fantasy',
                  'Historical', 'Horror', 'Mystery', 'Paranormal', 'Romance',
                  'Science Fiction', 'Thriller', 'Young Adult']
    limit_genre = st.sidebar.multiselect('Only Include Below Genres?',
                                         genre_list, default=None)

    num_input_text = """Genre Similarity Slider"""
    num_input = st.sidebar.slider(num_input_text, value=5,
                                  min_value=0, max_value=10)

    user_val_genres = list_to_text(user_val['genre'])
    user_val_title = user_val['title']
    st.sidebar.markdown(f"""**{user_val_title}** is listed under the following
    genres: {user_val_genres}""")

    recs_df = book_rec(user_val, matrix=desc_similarity, book_id='unique_id',
                       genres=limit_genre, overlap=num_input, author=author_check)
    recs_df = recs_df.iloc[1:]


recs_df.rename({'title': 'Title', 'author': 'Author', 'desc': 'Description',
                'genre': 'Genres', 'cover_link': 'Cover', 'unique_id': 'Book ID',
                'query_table_index': 'query_table_index'}, axis=1, inplace=True)
recs_df = recs_df[['Book ID', 'Cover', 'Title', 'Author', 'Description',
                   'Genres']]


recs_df['Cover'] = recs_df['Cover'].apply(html_image)
recs_df['Genres'] = recs_df['Genres'].apply(list_to_text)
recs_df['Description'] = recs_df['Description'].str.replace("###", "<br />",
                                                            regex=False)
recs_df['Description'] = recs_df['Description'].str.replace("#", "",
                                                            regex=False)

recs_df = recs_df.to_html(escape=False, index=False, justify='center')
st.markdown(recs_df, unsafe_allow_html=True)
