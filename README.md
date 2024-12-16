# backend-grok-integration
INSTRUCTION TO RUN THE PROJECT
STEP1:travers to the rooot directory and download the node modules, command npm i
STEP2: download the necessary pyhthon dependies requires
STEp3:start the server node ./bin/www
Step 4: Access the Application
Once the server starts successfully, you can access the application in your browser at the following URL:http://localhost:3000


routes
GET /: Renders the home page (index view).
GET /demo: Renders an input form page (input_form view).
GET /chatbot: Renders the chatbot page (chatbot view).
POST /query: Receives a query, processes it using a Python script, and returns the response.
GET /status: Returns the status of the server (typically active).
POST /update: Updates the knowledge base by crawling a website, scraping data, and storing it.
