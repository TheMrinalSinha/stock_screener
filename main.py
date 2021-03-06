from turtle import forward
import models
import yfinance         as yf
from fastapi            import FastAPI, Request, Depends, BackgroundTasks
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm     import Session
from database           import SessionLocal, engine
from pydantic           import BaseModel
from models             import Stock

models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

class StockRequest(BaseModel):
    symbol: str

def get_db():
    """
    this function helps us to get the database session
    """
    try:
        db = SessionLocal()
        yield db
    finally:
        db.close()

@app.get("/")
def home(request: Request, db: Session = Depends(get_db)):
    """
    Displays the stock screener homepage
    """
    stocks = db.query(Stock)

    _filters = request.query_params
    # TODO: exact filter as passed in query_params
    # stocks   = stocks.filter_by(**dict(_filters))

    _ma_50          = _filters.get("ma_50")
    _ma_200         = _filters.get("ma_200")
    _forward_pe     = _filters.get("forward_pe")
    _dividend_yield = _filters.get("dividend_yield")

    if _ma_50:
        stocks = stocks.filter(Stock.price > Stock.ma50)

    if _ma_200:
        stocks = stocks.filter(Stock.price > Stock.ma200)

    if _forward_pe:
        stocks = stocks.filter(Stock.forward_pe < _forward_pe)

    if _dividend_yield:
        stocks = stocks.filter(Stock.dividend_yield > _dividend_yield)


    return templates.TemplateResponse("home.html", {
        'request': request,
        'stocks' : stocks.all(),
        **_filters,
    })

def fetch_stock_data(id: int):
    db = SessionLocal()
    stock = db.query(Stock).filter(Stock.id == id).first()

    yf_data = yf.Ticker(stock.symbol)
    stock.ma50           = yf_data.info.get('fiftyDayAverage')
    stock.ma200          = yf_data.info.get('twoHundredDayAverage')
    stock.price          = yf_data.info.get('previousClose')
    stock.forward_pe     = yf_data.info.get('forwardPE')
    stock.forward_eps    = yf_data.info.get('forwardEps')
    stock.dividend_yield = yf_data.info.get('dividendYield')

    db.add(stock)
    db.commit()


@app.post("/stock")
def create_stock(stock_request: StockRequest, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """
    Created a stock and store it in the database
    """
    stock = db.query(Stock).filter(Stock.symbol == stock_request.symbol).first()
    if not stock:
        stock = Stock()
        stock.symbol = stock_request.symbol
        db.add(stock)
        db.commit()

    background_tasks.add_task(fetch_stock_data, stock.id)

    return {
        "code":    "success",
        "message": "stock created successfully",
    }
