import redis
import json

r = redis.Redis(host='redis', port=6379, db=0)

# r.rpush('recording_queue', json.dumps({
#     "choice": "zoom",
#     "meeting_url": "https://zoom.us/test"
# }))

r.rpush('recording_queue', json.dumps({
    "choice": "gmeet",
    "meeting_url": "https://meet.google.com/uju-omvv-yia"
}))


print("Message pushed to 'recording_queue' successfully.")