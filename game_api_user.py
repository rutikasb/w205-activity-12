#!/usr/bin/env python
import json
from kafka import KafkaProducer
from flask import Flask, request

app = Flask(__name__)
producer = KafkaProducer(bootstrap_servers='kafka:29092')


def log_to_kafka(topic, event):
    print(event)
    event.update(request.headers)
    producer.send(topic, json.dumps(event).encode())


@app.route("/")
def default_response():
    default_event = {'event_type': 'default'}
    log_to_kafka('events', default_event)
    return "This is the default response!\n"


@app.route("/purchase_a_sword")
def purchase_a_sword():
    # get request parameters/arguments
    sword_type = request.args.get("sword_type")

    # logic to get username from session info goes here, but harcoding it for now
    username = 'Rutika and Arvind'
    purchase_sword_event = {'event_type': 'purchase_sword',
                            'sword_type': sword_type,
                            'user': username}
    log_to_kafka('events', purchase_sword_event)
    return "Sword Purchased of type {}!\n".format(sword_type)

@app.route("/purchase_a_knife")
def purchase_a_knife():
    purchase_knife_event = {'event_type': 'purchase_knife',
                            'description': 'very sharp knife'}
    log_to_kafka('events', purchase_knife_event)
    return "Knife Purchased!\n"