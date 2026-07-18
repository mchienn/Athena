"""ASGI gateway for Firebase Hosting's booking URL prefix."""

from fastapi import FastAPI

from hanoi_heart_assistant.service import app as booking_service


app = FastAPI(title="Athena Booking Gateway")
app.mount("/booking-api", booking_service)
