mkdir -p ~/.streamlit/

echo "\
[server]
headless = true
enableCORS=false
port = 8501
" > ~/.streamlit/config.toml
