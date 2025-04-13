# Manimator
Manimator is a web application that allows you to create manim animations.

## Features
- You can write any idea you have in mind and the app will generate a manim vid
- You can also just add a link of an arxiv paper 
- You can also upload pdfs 

## Coming Soon
- generation from youtube videos, slides, docs .
- better fallback system.
- more examples and improved videos.

## How can you help?

- I don't store any data and the app is open source so your feedback is really important.
- I would really appreaciate if you could send manim examples that you would like to see generated. ( give the code )
- You can also help by giving feedback on the generated videos. ( what you like and what you don't like )
- Give the prompts where model was fail to generate the video. ( i can go back and add examples to guide.md so model can learn from it and not make the same mistake)
- You can also help by giving money if you are filthy rich ( i can possibly train on manim docs and exmaples ( which might improve accuracy) )




# Docker Running
- Grab the image from docker hub by doing:
```sh
docker pull mostlyk/manimator
```
- Then run the image with:
```sh
docker run -p 8501:8501 -e GEMINI_API_KEY='your_api_key mostlyk/manimator
```

# Hosted on Hugging Face Spaces
- You can also see the app on Hugging Face Spaces. The app is hosted at:

 https://huggingface.co/spaces/mostlyk/Manimator

# Running Locally

- To run the app locally, you can use Docker or install the dependencies manually.
- Make sure you have .env file in the root directory with the following content:
```sh
GEMINI_API_KEY='your_api_key'
```
- Replace `your_api_key` with your actual Gemini API key. You can get it from the Gemini website.

## Using Docker

```sh
docker build -t manimator .
docker run -p 8501:8501 -e GEMINI_API_KEY='your_api_key' manimator
```
- Then open your browser and go to `http://localhost:8501`.

## Manually
### Using Conda
- Create a conda environment with the required dependencies:
```sh
conda env create -f environment.yml
```
- Activate the environment:
```sh
conda activate manimator
```
- Install the dependencies:
```sh
pip install -r requirements.txt
```
- Run the app:
```sh
streamlit run src/app.py
```
- Then open your browser and go to `http://localhost:8501`.
### Using Virtualenv
- Create a virtual environment:
```sh
python -m venv venv
```
- Activate the virtual environment:
```sh
source venv/bin/activate  # On Windows use `venv\Scripts\activate`
```
- Install the dependencies:
```sh
pip install -r requirements.txt
```
- Run the app:
```sh
streamlit run src/app.py
```
- Then open your browser and go to `http://localhost:8501`.
