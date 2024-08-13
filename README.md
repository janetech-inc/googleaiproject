# Google AI Project


### Setup 

#### Requirements:

- Python
- Pip

### Environment
- ```GEMINI_API_KEY```: The API key for Google Gemeni. Defaults to "".
- ```CONTENT_PATH```: The content directory key for storing output. Defaults to `.\tmp\output`
- 

### To run locally


  
```
pip install -r requirements.txt
python app/main.py
```

### To run locally with docker

```
docker compose up --build
```
### To deploy to AWS

#### 1. Install AWS

#### 2. Set AWS profile
```

```
#### 2. Run serverless deploy
```
npm install
serverless deploy --stage dev
```
