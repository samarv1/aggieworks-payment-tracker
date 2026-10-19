from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime
from threading import Lock
from scraper import scrape_emails
from csv_handler import save_payments_to_csv, get_payment_count

app = FastAPI(title="AggieWorks Payment Tracker API")
_scrape_lock = Lock()

# CORS middleware to allow frontend to call backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request model for scraper configuration
class ScraperConfig(BaseModel):
    email: str
    startDate: str
    startTime: str
    category: Literal["retreat", "dues", "other"]
    customKeywords: Optional[str] = None
    source: Literal["venmo", "zelle", "both"] = "venmo"  # Default to 'venmo', can be 'venmo', 'zelle', or 'both'


# Response model
class ScraperResponse(BaseModel):
    status: str
    message: str
    data: Optional[dict] = None


@app.get("/")
async def root():
    """Health check endpoint"""
    return {"message": "AggieWorks Payment Tracker API is running"}


@app.post("/api/scraper/run", response_model=ScraperResponse)
def run_scraper(config: ScraperConfig):
    """
    Endpoint to receive scraper configuration and trigger email scraping

    Args:
        config: ScraperConfig object containing email address,
                start datetime, category, and optional custom keywords

    Returns:
        ScraperResponse with status and results
    """
    if not _scrape_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="A payment search is already running.")
    try:
        # Log the selected search parameters
        print(f"Received scraper request:")
        print(f"  Email: {config.email}")
        print(f"  Start Date: {config.startDate}")
        print(f"  Start Time: {config.startTime}")
        print(f"  Category: {config.category}")
        print(f"  Source: {config.source}")
        if config.customKeywords:
            print(f"  Custom Keywords: {config.customKeywords}")

        # Combine date and time into a single datetime string
        start_datetime_str = f"{config.startDate} {config.startTime}"

        # Parse to validate datetime format
        try:
            start_datetime = datetime.fromisoformat(start_datetime_str)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid date/time format"
            )

        # Call scraper function(s) based on source
        print("Starting email scrape...")
        all_payments = []

        if config.source == "both":
            # Scrape both Venmo and Zelle
            venmo_payments = scrape_emails(
                email=config.email,
                start_datetime=start_datetime,
                category=config.category,
                keywords=config.customKeywords,
                source='venmo'
            )
            print(f"Found {len(venmo_payments)} Venmo payment(s)")

            zelle_payments = scrape_emails(
                email=config.email,
                start_datetime=start_datetime,
                category=config.category,
                keywords=config.customKeywords,
                source='zelle'
            )
            print(f"Found {len(zelle_payments)} Zelle payment(s)")

            all_payments = venmo_payments + zelle_payments
        else:
            # Scrape single source
            all_payments = scrape_emails(
                email=config.email,
                start_datetime=start_datetime,
                category=config.category,
                keywords=config.customKeywords,
                source=config.source
            )

        print(f"Found {len(all_payments)} total payment(s)")

        # Save to CSV
        csv_path, total_amount = save_payments_to_csv(
            all_payments, config.category, start_datetime_str, config.source,
            email=config.email, custom_keywords=config.customKeywords,
        )
        total_in_csv = get_payment_count()

        source_label = "Venmo & Zelle" if config.source == "both" else config.source.capitalize()

        return ScraperResponse(
            status="success",
            message=f"Successfully scraped {len(all_payments)} incoming {source_label} payment(s). Total in CSV: {total_in_csv}",
            data={
                "new_payments": all_payments,
                "new_count": len(all_payments),
                "total_in_csv": total_in_csv,
                "total_amount": total_amount,
                "csv_path": csv_path,
                "category": config.category,
                "start_datetime": start_datetime_str
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error processing scraper request: {str(e)}"
        )

    finally:
        _scrape_lock.release()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)

