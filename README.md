<div align="center">
  <img src="resources/logo_big.png" alt="TrendLine Logo" width="400"/>
</div>

# TrendLine

### Project Description

I want it to work the same way as it would if a person were to trade stocks based on news data (only I want it to be automated). So for a person trading stocks on news data, I think this pipeline would be correct:
- Person sees an article or headline saying something positive or negative about a particular stock.
- Person goes and trades stocks based on that info. Buying if they hear positive news, or selling if they hear negative news (and they have purchased that stock in the past).


So for automation of this process, here is how I see it working:
- A program scrapes news data from websites during market hours. It scrapes data at some regular interval (10 mins for example). 
   - The websites that are being scraped can be a pre-determined list. We want the news that we trade on to be reliable. Therefore we can have a pre-determined list of reliable news websites that we can repeatedly check. 
- I think we can limit the scope of this project to buying stock for positive sentiment headlines, then selling after a fixed amount of time. Obviously you can do much more sophisticated algorithms to determine when to sell. For the sake of getting something working, we will simply buy when there is positive market sentiment, and sell a fixed (but configurable) amount of time later.
   - If the market is close (or will be closed) after the fixed amount of time to sell, we can simply sell during market close or market open the next day.
- There is a challenge I can forsee. We need to associate each headline with a company, which I think is easier said than done. Most likely some type of NLP will be needed here to extract the company name (if there is one) from each news headline. 
   - If this task doesn't seem feasible, we can simply get a list of publicly traded company names from somewhere and reference against that list. 
   - This public traded list of companies may be necessary anyway so we can look up the ticker symbols for each company once we associate the headline with a company.
- We will need everything in the app to be well logged so we have good traceability of what happened.
- We will need to have hard (configurable) caps on the $ amount we are allowed to buy in total, and for each individual company. 



What if multiple positive headlines appear for the same company?
- In this case we will average sentiments across the different headlines.

How are duplicate headlines handled?
- If the headlines are from different websites, I think it's fine to average them. If they are from the website we probably need to delete one since that would be a true duplicate.

Will there be stop-loss mechanisms to prevent major losses?
- We will need to implement stop loss mechanisms. This would most likely be applicable in the case of a mis-classified sentiment (very negative mis-classified as very positive). We can set some sort of percentage threshold which will be configurable in the app. 

How many shares (or how much $) to buy per positive headline?
- We can start with a fixed amount of money (assuming we can buy partial shares). Then we can develop a more sophisticated algorithm later to buy more stock based on confidence. 

How will ambiguous company names be handled (e.g., "Apple" the company vs the fruit)?
- We will probably need some sort of NLP to classify if the headline is about a company or not. This will take some reasearch since I'm not sure what kind of model would do this yet.

Will the scraper only run during market hours, or continuously?
- The scraper will probably run continuously. We will need different logic to handle headlines that trigger stock buying while the market is open vs closed.
- Market closed logic: If a "buy" is triggered while the market is closed, buy as soon as the market opens. However, the "hold" timer doesn't start until the purchase happens.

How will pre-market and after-hours trading be handled?
- I need to look into this to understand it better. I understand it means extended hours which you can trade in but I don't understand who has access to it or when they have access.

Where will trade history be stored?
How will scraped headlines be archived?
- We will need a database to store trade history as well as a database to store headlines that were pulled. One question is, do we need to store all headlines that were pulled? Or can we just store the ones that triggered a buy.

App visualizations (streamlit web app)
- We will need a plot (interactive plotly line plot) to visualize how much money we have over time.
- In addition, we will want a table for any currently held positions to show if we are up or down for them.