from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from scraper import scrape_emails
from csv_handler import save_payments_to_csv, get_csv_path, csv_exists, get_payment_count

app = FastAPI(title="AggieWorks Payment Tracker API")

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
    password: str
    startDate: str
    startTime: str
    category: str
    customKeywords: Optional[str] = None


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
async def run_scraper(config: ScraperConfig):
    """
    Endpoint to receive scraper configuration and trigger email scraping
    
    Args:
        config: ScraperConfig object containing email credentials, 
                start datetime, category, and optional custom keywords
    
    Returns:
        ScraperResponse with status and results
    """
    try:
        # Log the received configuration (without password for security)
        print(f"Received scraper request:")
        print(f"  Email: {config.email}")
        print(f"  Start Date: {config.startDate}")
        print(f"  Start Time: {config.startTime}")
        print(f"  Category: {config.category}")
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
        
        # Call scraper function
        print("Starting email scrape...")
        payments = scrape_emails(
            email=config.email,
            password=config.password,
            start_datetime=start_datetime,
            category=config.category,
            keywords=config.customKeywords
        )
        
        print(f"Found {len(payments)} new payment(s)")
        
        # Save to CSV
        csv_path = save_payments_to_csv(payments, config.category)
        total_in_csv = get_payment_count()
        
        return ScraperResponse(
            status="success",
            message=f"Successfully scraped {len(payments)} incoming Venmo payment(s). Total in CSV: {total_in_csv}",
            data={
                "new_payments": payments,
                "new_count": len(payments),
                "total_in_csv": total_in_csv,
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

