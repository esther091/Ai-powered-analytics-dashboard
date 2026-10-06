# Online Retail II: analyst findings

Dataset: [Online Retail II](https://archive.ics.uci.edu/dataset/502/online+retail+ii) (UCI), every transaction of a
UK-based online gift-ware retailer from 1 Dec 2009 to 9 Dec 2011. Many customers are wholesalers. All figures
below come from the dashboard's API and can be reproduced from it; "valid sales" means the cleaned definition below.

## 1. Data quality and cleaning

| Step | Rows affected | Treatment |
|---|---:|---|
| Raw transactions | 1,067,371 | Matches the UCI row count (two Excel sheets combined). |
| Exact duplicate lines | 34,335 | Removed (keep first). |
| Cancellations (invoice starts with `C`) | 19,494 | Excluded from sales, tracked separately as cancelled value. |
| Non-product codes (postage, fees, manual adjustments, bank charges, tests) | 5,835 | Excluded from product revenue. |
| Zero or negative price lines | 6,207 | Excluded (mostly stock write-offs and adjustments). |
| Two erroneous bulk orders (80,995 and 74,215 units) | 4 | Excluded with their immediate cancellations. |
| Lines without a customer ID | 243,007 (23%) | Kept for revenue and orders; excluded from customer analytics. They make up 13% of revenue. |
| **Valid sales** | **1,003,413** | **£19.40M revenue, 39,514 orders, 5,852 identified customers, 43 countries.** |

Country names were normalised (EIRE to Ireland, RSA to South Africa, USA to United States).

## 2. Headline: a flat business, bought differently

Twelve months to November 2011 against the twelve months before:

| | Dec 2009 - Nov 2010 | Dec 2010 - Nov 2011 | Change |
|---|---:|---:|---:|
| Revenue | £9.40M | £9.56M | **+1.7%** |
| Orders | 19,743 | 18,956 | -4.0% |
| Average order value | £476 | £504 | +5.9% |
| Units | 5.63M | 5.17M | -8.0% |
| Active customers | 4,239 | 4,292 | +1.3% |
| Cancelled value (% of gross) | 2.5% | 3.2% | +0.7 pts |

Revenue held up because each order got bigger, not because there were more of them. Fewer units at a higher
order value points to a mix shift towards pricier lines (or price rises).

**Within 2011 the picture changed sharply.** March and April 2011 were 9-20% below 2010, while May to September
were 6-18% above. Cancellations in calendar 2011 nearly doubled to 4.8% of order value (2.6% in 2010), the
single most worrying trend in the data.

## 3. Seasonality and timing

- **September to November is 37% of the year's revenue**, peaking in November (£1.45M in 2011). Stock and
  marketing plans need to land by late August.
- The shop is effectively closed on Saturdays and over Christmas and New Year.
- Revenue peaks on **Thursdays around 12:00**; trading runs roughly 07:00 to 20:00, with Sunday a lighter,
  smaller-basket day (average order £370 vs £500-550 on Monday and Tuesday).

## 4. Markets

The UK is 85% of revenue and was flat year on year (-0.0%). Growth came from abroad (12 months to Nov 2011 vs prior):

| Country | Revenue | Change |
|---|---:|---:|
| Netherlands | £272k | +2% |
| Ireland | £264k | **-25%** |
| Germany | £198k | +11% |
| France | £178k | +41% |
| Australia | £138k | ×4.7 |
| Spain | £55k | +32% |
| Switzerland | £53k | +30% |

The Netherlands, Ireland and Australia are a handful of wholesale accounts each (3 to 22 customers) with average
orders of £1k to £3k, so they are account-management relationships rather than consumer markets. Ireland's
25% fall is worth a direct conversation with those three accounts.

## 5. Products

- **22% of products make 80% of revenue** (about 1,040 'A' products all time). Top seller: Regency Cakestand 3 Tier
  (£331k), then White Hanging Heart T-Light Holder.
- Fast risers in 2011 include Rabbit Night Light (launched in 2011, £62k in the second half), Paper Chain Kit
  50's Christmas and Hot Water Bottle Keep Calm.
- **Strong cross-sell pairs** (market basket analysis): Regency tea-set pieces (sugar bowl, milk jug, teapot,
  plates), Poppy's Playhouse bedroom and kitchen, matching coloured party cups/plates/candles. Confidence of
  60-85% and lift of 30-40×: these should be bundled or recommended together on product pages.

## 6. Customers

- **Revenue is concentrated: the top 10% of customers bring 63% of revenue.**
- **28% of customers ordered only once.** On average only about 21% of a month's new customers order again the
  next month (cohort analysis, excluding the first, left-censored cohort).
- RFM segmentation (K-means, 4 clusters chosen by silhouette score):

| Segment | Customers | Share of revenue | Median days since last order | What to do |
|---|---:|---:|---:|---|
| Champions | 1,183 (20%) | 73% | 17 | Reward and retain; don't discount. |
| At risk | 1,453 (25%) | 17% | 184 | Win-back campaign: they used to order regularly. |
| New & promising | 1,246 (21%) | 6% | 24 | Second-order incentive within 30 days. |
| Hibernating | 1,970 (34%) | 4% | 401 | Low-cost reactivation only. |

## 7. Predictive models

| Model | Purpose | Result |
|---|---|---|
| Churn classifier (gradient-boosted trees) | Probability a customer orders nothing in the next 90 days | ROC AUC **0.79** on held-out customers (base rate 56%). 1,401 currently active customers are high risk. Days since last order is by far the strongest signal, followed by the usual gap between orders. |
| Revenue forecast (GBM on calendar features blended with growth-adjusted seasonal naive) | Weekly revenue for the next 90 days | 13-week backtest error 16% per week, on par with "same week last year" (16%). Forecast: **£476k for the 30 days after 9 Dec 2011** (includes the Christmas shutdown) and £1.70M over 90 days. |
| Anomaly detection (Isolation Forest) | Flag unusual trading days | Flags about 3% of days; most are quiet Sundays or pre-Christmas days with unusually few orders, plus big-wholesale-order days (for example 27 Sep 2010 and 20 Sep 2011). |

Two years of history is a short series for forecasting, so the forecast should be read as a planning range,
not a target. For small countries the backtest error is too high to be useful and the dashboard says so.

## 8. Recommendations

1. **Investigate the doubling of cancellations in 2011** (2.6% to 4.8% of order value). Break it down by product
   and customer; the dashboard's "Ask the data" can do this conversationally.
2. **Launch a win-back programme for the 1,453 'At risk' customers** (17% of historical revenue), starting with the
   highest value-at-risk accounts listed on the Customers page.
3. **Fix the second order.** With 28% one-time buyers and ~21% month-1 return, an onboarding offer for new
   customers is the cheapest growth lever.
4. **Plan for September to November** (37% of revenue): stock the 'A' products and the 2011 risers early.
5. **Treat international wholesale as key accounts**: France and Australia are growing fast; Ireland needs attention.
6. **Bundle the strong cross-sell pairs** (Regency tea set, Poppy's Playhouse, matching party ranges).

## Limitations

No cost, margin, marketing or stock data, so this is revenue analysis, not profitability. 23% of lines have no
customer ID, so customer metrics cover 87% of revenue. December 2011 is partial (ends on the 9th).
