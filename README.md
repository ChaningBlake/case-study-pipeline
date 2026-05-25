# Case Study Pipeline

This project shows a mock flask application that handles content distribution for the Original Content Services team.
See 'Getting Started' below to run the project, or .

Note: Logging has been redirected to stdout for development purposes. Claude was used to create `test_app.py` from the Submission Criteria in the document.

#### Project Structure
```
case-study-pipeline/
|-- README.md
|-- data/
| |-- assets_seed.json <- 12 seed media assets (read-only)
| +-- platforms.json <- 5 distribution platforms (read-only)
|-- starter/
| |-- app.py <- Your implementation goes here
| +-- requirements.txt
+-- webhook_receiver/
|-- receiver.py <- Test helper: observe webhook calls
+-- requirements.txt
```

#### Getting Started
```
# Terminal 1 — webhook receiver (recommended for testing Endpoint 5)
cd webhook_receiver
pip install -r requirements.txt
python receiver.py
# Listening on http://localhost:5001
# Terminal 2 — your API
cd starter
pip install -r requirements.txt
python app.py
# Running on http://localhost:5000
# Terminal 3 - tests
cd starter
python -m pytest -v test_app.py
```

## Further Consideration
Below are some additional considerations for productionalizing this application:

### Authentication
I would add authentication to these endpoints to ensure only allowed parties have access and to prevent bad actors from sending requests to our webhooks. Additionally, authorization could be added if permissions to create/update jobs is restricted.

### Layered Architecture
I would consider introducing a layered architecture with dependency injection. These layers often consist of a route, logic, and data layer. This helps keep business logic and data access patterns loosely coupled. If we choose to change how we store data in the future, injecting a different data layer makes this an easier change. 

### Asynch Queue
For the purposes of this mock application, I stored DeliveryJobs in memory and used the threading module to run posts
to webhooks asynchronously. However, this is not ideal for a production application. If the application crashed these jobs could be lost. Metadata about DeliveryJobs could be stored in a table, and the job could be submitted to a queue (e.g. AWS SQS).

### Cache Stats
I currently compute the stats on every call to `/api/stats`. However, this might not be performant at scale. The results could be cached with a low time to live or the stats could be stored and updated as they change. This would allow values to simply be read instead of calculated on each call.