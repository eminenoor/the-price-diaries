# How it works

## Fake sales

A sale is flagged as fake when, within the last 14 days, the price rose at least 5% to a peak, has since dropped, and the "sale" price is still no lower than before the rise (within 2%).

## Unusual rises

Day-to-day log returns are scored with the modified z-score (Iglewicz & Hoaglin, 1993):

$$M_i = \frac{0.6745 (r_i - \tilde{r})}{\text{MAD}}$$

- $\tilde{r}$ is the median return and MAD is the median absolute deviation
- Rises with $M_i > 3.5$ are flagged
- Median and MAD are used instead of mean and standard deviation because they aren't distorted by the spikes being looked for
- A product that changes price daily needs a bigger jump to be flagged than one that's usually stable

Both checks are in `backend/src/price_diaries/analysis.py`.

## Stores that block automated checks

When a store refuses a check, the product shows "Last check failed" with the reason instead of a price. The app doesn't try to get around these blocks. As of November 2026:

- Sephora blocks both plain page downloads and the browser, so its prices can't be tracked
- Watsons blocks the browser, but plain page downloads work, so regular prices are tracked
- Eve Shop answered "too many requests" (429) during testing; try again later

## Security and responsible scraping

- Every product URL must be HTTPS, on a known store domain, with no credentials or custom ports. This blocks requests to `localhost`, private IPs and cloud metadata endpoints (`backend/src/price_diaries/security.py`).
- The server listens only on `127.0.0.1` because the app has no login.
- One request at a time per store, a random 3 to 7 second pause, `robots.txt` respected, and one check a day.
- For personal, educational use. Store terms of service may restrict automated access (Amazon, for example, prohibits it). Collected prices are never committed to the repository.
