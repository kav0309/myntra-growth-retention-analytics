# Interview Guide — How to Present This Project

## 30-second version

“I built a Myntra-inspired growth analytics case study using a public multi-table fashion e-commerce dataset. I joined clickstream sessions to transactions, built an AARRR framework, and focused on repeat-purchase retention. The interesting finding was that promo-acquired buyers appeared to have an 18% relative D30 retention penalty, but after controlling for acquisition month the gap fell to about 0.5 percentage points. So instead of concluding discounts create bad customers, I proposed a randomized post-purchase loyalty experiment and built an interactive lift-sizing model.”

## 2-minute walkthrough

### 1. Why this project?
Fashion marketplaces rely heavily on promotions. The product question was whether sales drive temporary conversion at the cost of retention, and where the growth team should intervene after acquisition.

### 2. What data did you use?
A public Kaggle e-commerce dataset with four linked tables: customers, products, clickstream events and transactions. It is not Myntra proprietary data; Myntra is the product context and visual inspiration.

### 3. What did you build?
- session-level journey funnel
- AARRR metric map
- first-purchase cohorts
- D7/D30/D60/D90 cumulative repeat-purchase retention
- promo vs non-promo first-purchase cohorts
- month-adjusted retention comparison
- monthly cohort heatmap
- traffic/payment/category views
- interactive retention-lift scenario model

### 4. What was the most important finding?
The raw D30 rate was 20.3% for non-promo first buyers and 16.7% for promo first buyers. That looks like a 3.7 pp or 18.1% relative penalty.

But the groups were acquired in different calendar periods. I re-ran the comparison within first-purchase month and standardized the results. The gap dropped to ~0.5 pp.

That changed the recommendation: **do not infer that discounting causes poor retention from the raw chart.**

### 5. What would you do next?
Randomize a post-purchase lifecycle intervention among first-time promo buyers:

- control: existing journey
- treatment: D7–D14 personalized category recommendation + loyalty milestone before D30
- primary metric: second successful purchase within 30 days
- guardrails: AOV, incremental discount cost, failed-payment rate

The dashboard's 18% lift is only a scenario for sizing. It is not claimed as observed causal impact.

---

## Questions an interviewer may ask

### “Why did you call this Myntra-inspired if the data isn't Myntra?”
Because public Myntra user-level behavioral data is not available. I separated the **business context** from the **data provenance** and disclose that clearly. The methodology is designed for a fashion marketplace like Myntra, but the dataset is public Kaggle data.

### “Why is your add-to-cart rate so high?”
The clickstream is transaction-centered and most sessions are commerce journeys. I explicitly flag that limitation and do not use the funnel as an external benchmark. I use it primarily to understand the available journey stages and payment completion.

### “Is promo causing lower retention?”
No causal claim. The raw association is negative, but month-standardization reduces it dramatically. That suggests cohort composition explains much of the raw difference. A randomized promo or lifecycle experiment is required for causal inference.

### “Why use second purchase as retention?”
The clickstream does not expose customer identity for every non-purchasing session, so user-level visit retention would be incomplete. Successful transactions do link reliably to customer IDs. I therefore use repeat-purchase retention, which is both observable and commercially meaningful.

### “What's the difference between 79.6% repeat buyers and 19% D30 retention?”
79.6% is an **ever-repeat** metric over a multi-year observation window. D30 retention asks whether a buyer repeats within 30 days. The gap between them shows that many customers eventually return, but not necessarily quickly.

### “Why not calculate LTV/CAC?”
There is no campaign-cost or acquisition-spend table. Calculating CAC would require inventing data. I would add campaign, channel cost, attribution and experiment tables before calculating retained CAC or LTV:CAC.

### “How did you adjust for cohort mix?”
I calculated D30 promo and no-promo rates inside each first-purchase month, kept months with sufficient sample size in both groups, and standardized both sets of rates using promo-cohort size as weights.

### “Why not use a regression?”
A regression could be a next step, but month-standardization is transparent and easy to audit. For a product decision, interpretability is valuable. With richer data, I would use randomized assignment first; otherwise regression/propensity methods could control additional confounders.

### “What does the 18% slider mean?”
It is a relative-lift assumption applied to the observed promo D30 baseline, then translated into incremental repeat buyers and second-order value using observed cohort size and second-order AOV. It is for experiment sizing, not a forecast.

### “What would referral instrumentation look like?”
At minimum: invite_sent, invite_opened, invite_accepted, referrer_customer_id, referred_customer_id, referred_signup and referred_first_order. Then measure invite conversion, referred-buyer D30 retention and K-factor.

---

## Strong takeaways to emphasize

- I did not force the data to support the original hypothesis.
- I changed the recommendation when cohort adjustment changed the result.
- I distinguished descriptive analysis from causal inference.
- I handled incomplete telemetry by redefining retention to something observable.
- I built an interactive business-facing artifact, not just a notebook.
- I documented limitations instead of hiding them.

## Things not to say

Avoid:
- “This is Myntra customer data.”
- “Promos reduce retention by 18%.”
- “My recommendations will improve retention by 18%.”
- “The funnel conversion is Myntra's conversion rate.”
- “I calculated referral performance.”

Use:
- “Myntra-inspired portfolio case study.”
- “The raw association was 18.1% relative, but most of it disappeared after cohort adjustment.”
- “I modeled an 18% lift scenario for experiment sizing.”
