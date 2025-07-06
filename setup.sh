mkdir -p ~/.streamlit/

echo "\
[general]\n\
email = \"din@email.se\"\n\
" > ~/.streamlit/credentials.toml

echo "\
[server]\n\
headless = true\n\
port = $PORT\n\
enableCORS = false\n\
" > ~/.streamlit/config.toml
