# Convorza AI



**An AI-powered conversational workspace for businesses.**



Convorza AI helps businesses manage customer conversations through an AI assistant, organize customer requests, and monitor activity through a business dashboard.



## Features



-**AI Customer Support:** Handles customer conversations using Google's Gemini AI.

- **Business Workspaces:** Separate workspaces for different businesses.

- **Business-Specific Assistants:** Configure assistant names, tones, FAQs and supported languages.

- **Customer Record Lookup:** Retrieve order or reservation information.

- **Request Management:** Create and update customer requests.

- **Owner Authentication:** Signup, login and logout functionality.

- **Business Dashboard:** View business activity and customer requests.



## Technology Stack



- **Frontend:** HTML, CSS, JavaScript

- **Backend:** Python, FastAPI

- **AI:** Google Gemini API

- **Database:** SQLite

- **Data Storage:** CSV and JSON files



## Project Structure



```text

convorza/

│

├── backend/

│   ├── main.py

│   ├── agent.py

│   ├── tools.py

│   ├── seed\_demo\_data.py

│   └── businesses/

│

├── frontend/

│   ├── index.html

│   ├── login.html

│   └── dashboard.html

│

├── requirements.txt

├── .gitignore

└── README.md

```



## Setup Instructions



### 1. Clone the repository



```bash

git clone https://github.com/Aniska1/convorza.git

cd convorza

```



### 2. Create a virtual environment



```bash

python -m venv venv

```



Activate it on Windows:



```bash

venv\\Scripts\\activate

```



### 3. Install dependencies



```bash

pip install -r requirements.txt

```



### 4. Configure your Gemini API key



Create a `.env` file in the project root directory:



```env

GEMINI\_API\_KEY=your\_gemini\_api\_key

```



Replace the placeholder with your own Gemini API key.



### 5. Run the application



```bash

cd backend

python -m uvicorn main:app --reload --host 127.0.0.1 --port 8001

```



Open the application at:



http://127.0.0.1:8001



API documentation:



http://127.0.0.1:8001/docs



## Demo Data



The repository includes sample business configurations and fictional customer records for demonstration purposes.



## Security



Never upload your `.env` file, API keys, passwords or private database files to GitHub.



\## Project



\*\*Convorza AI\*\* — Building smarter customer conversations for businesses.

