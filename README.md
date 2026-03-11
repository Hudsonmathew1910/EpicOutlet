# EpicOutlet — AI-Powered E-Commerce Web App

EpicOutlet is a full-featured e-commerce web app built with **Python** and **Django**. It supports multi-category product browsing, search, user accounts, cart + favourites, and an **AI shopping chatbot (Shop-Bot)** to help users find products using natural language.

## Features
- User authentication (register, login, account management)
- Product browsing by categories (Mobile, Fashion, Electronics, Home, Grocery)
- Product search, filtering, and sorting
- Shopping cart and favourites list
- Admin dashboard (manage products, categories, and orders) with **Jazzmin**
- **Shop-Bot (AI chatbot)** for natural-language shopping assistance
- Product/category images stored on **Cloudinary**
- REST API available at `/api/v1/` using **django-tastypie**
- Responsive UI with **Bootstrap**

## Tech Stack
- **Backend:** Python 3.11 / 3.13, Django 5.2
- **Database:** PostgreSQL (Supabase)
- **AI / LLM:** Groq API (GPT-OSS 120B) via OpenAI-compatible Python SDK
- **REST API:** django-tastypie
- **Images:** Cloudinary
- **Frontend:** Bootstrap 5.3, Font Awesome
- **Chat Rendering:** Marked.js (Markdown rendering in browser)
- **Static files:** WhiteNoise
- **Deployment:** Render (cloud), Gunicorn
- **Environment:** python-dotenv

## How Shop-Bot Works
Shop-Bot connects to the **Groq AI API** and uses a tool called `search_products` to query the database.  
It supports filters like **category**, **price range**, **vendor**, and **trending status**, then returns results formatted in Markdown for a clean chat UI.

## REST API
The project exposes endpoints under:
- `/api/v1/`

This allows external applications to access product and related data programmatically.

## Deployment Notes
EpicOutlet is production-ready and can be deployed with:
- **Gunicorn** as the WSGI server
- **WhiteNoise** for serving static files
- **Cloudinary** for media storage

## Project Highlights
- Reduces manual product search by enabling natural-language queries (example: “phones under ₹30,000”)
- Scales media delivery via Cloudinary CDN
- Provides a reusable REST API for integrations
- Works smoothly on mobile and desktop with Bootstrap

## Author
Built by **Hudson Mathew** — December 2025
