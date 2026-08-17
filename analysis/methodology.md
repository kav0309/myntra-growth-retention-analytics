# Methodology & Metric Definitions

This document defines exactly how the dashboard metrics are calculated and where the analysis should **not** be over-interpreted.

## 1. Source tables

The project uses the public **E-commerce App Transactional Dataset** by Aditya Bagus Pratama on Kaggle:

`https://www.kaggle.com/datasets/bytadit/transactional-ecommerce`

The source contains four logical tables:

- `customer.csv` — 100,000 registered customers
- `product.csv` — fashion-oriented catalog taxonomy
- `click_stream.csv` — application event history keyed by `session_id`
- `transactions.csv` — order/payment records linking `customer_id` and `session_id`

The source dataset is not committed to this repository. Only aggregate analytical outputs are included.

## 2. Data window

Successful transactions span approximately **2016-06-30 through 2022-07-31**.

The uploaded analysis dataset contains:

- 895,203 unique clickstream journeys/sessions
- 852,584 transaction rows
- 815,964 successful transactions
- 50,242 customers with at least one successful transaction

Two transaction session IDs do not appear in the summarized clickstream. That is negligible for the analysis but is kept as a quality check.

## 3. Successful purchase

A transaction counts as successful when:

```text
payment_status == "Success"
```

Failed payments are excluded from purchase-retention and order-value calculations.

## 4. Funnel definition

The dashboard's displayed journey funnel is:

```text
Homepage/journey → Add to cart → Booking → Successful payment
```

The first three stages use session-level clickstream flags. Successful payment is joined from the transaction table by `session_id`.

### Important caveat

The source clickstream is strongly transaction-centered. More than 95% of summarized sessions contain booking behavior. This is not representative of a normal marketplace's full visitor funnel and should **not** be cited as a Myntra conversion benchmark.

`SEARCH`, `ITEM_DETAIL`, `PROMO_PAGE`, and `ADD_PROMO` are shown as behavioral signals rather than required sequential funnel stages because users can follow different paths.

## 5. Acquisition and activation

**Registered customer:** distinct `customer_id` in the customer table.

**Successful buyer:** customer with at least one successful transaction.

**Registered-to-successful-buyer rate:**

```text
successful buyers / registered customers
```

This is a long-window conversion, not a bounded 7-day or 30-day activation rate.

**Signup-to-first-purchase time:**

```text
first successful transaction timestamp - first_join_date
```

All successful buyers in the source have non-negative signup-to-first-purchase lag.

## 6. Promo cohort definition

A customer's acquisition purchase is their **first successful transaction**.

A buyer is classified as promo-acquired if:

```text
promo_amount > 0
```

on that first successful transaction.

The non-promo cohort is the complement.

## 7. D7 / D30 / D60 / D90 repeat-purchase retention

Retention is cumulative second-purchase retention.

For a window `D`:

```text
retained_D = second successful purchase occurs within D days of first successful purchase
```

A customer is included only when their first purchase occurred at least `D` days before the dataset ends. This avoids right-censoring users who did not have a complete observation window.

This metric is deliberately called **repeat-purchase retention**, not app/session retention.

## 8. Raw sale vs non-sale comparison

For mature cohorts, calculate:

```text
D30 rate, promo-acquired
D30 rate, no-promo
```

Observed result:

- No promo: ~20.34%
- Promo: ~16.67%
- Raw gap: ~3.68 percentage points
- Relative gap: ~18.07% vs the non-promo benchmark

This is descriptive, not causal.

## 9. Acquisition-month adjustment

The raw result is confounded because promo and non-promo users have different calendar-cohort composition.

The adjustment used here is transparent standardization rather than a black-box model:

1. Assign every buyer to first-purchase calendar month.
2. Compute promo and no-promo D30 repeat rate inside each month.
3. Keep months with at least 50 mature buyers in each group.
4. Weight both month-specific rates by the promo cohort size in that month.
5. Compare the standardized rates.

Result:

- Standardized no-promo D30: ~17.19%
- Standardized promo D30: ~16.65%
- Adjusted gap: ~0.54 percentage points

Interpretation: most of the headline raw gap is explained by cohort composition. This still does **not** prove zero causal promo effect; randomized assignment would be required for that.

## 10. Monthly cohort heatmap

Each customer's cohort is the month of first successful purchase.

For each cohort and activity month:

```text
monthly retention = customers with ≥1 successful purchase in activity month / cohort size
```

The dashboard displays M0–M6 for 2021 cohorts.

This is **non-cumulative monthly activity retention**. A later cell can be larger than an earlier cell because customers can skip one month and return in another.

## 11. Revenue/value definitions

`total_amount` is treated as **successful order value / GMV proxy** and is not converted to INR.

```text
successful order value = SUM(total_amount) for successful transactions
AOV = MEAN(total_amount) for successful transactions
```

The dataset's monetary units are left unchanged and displayed as `SU` (source units) in the dashboard.

For product-category mix:

```text
merchandise value = item_price × quantity
```

This is calculated before transaction-level promo deductions and therefore is shown separately from successful `total_amount`.

## 12. Repeat-buyer rate

```text
ever-repeat buyer = successful buyer with at least 2 successful transactions anywhere in the observation window
```

This is a long-run descriptive metric and should not be confused with D30 retention.

## 13. Scenario model

The retention slider is a **what-if sizing tool**.

For a selected relative lift `L`:

```text
incremental repeat buyers
= mature promo buyers × observed promo D30 rate × L

incremental second-order value
= incremental repeat buyers × observed promo-cohort second-order AOV
```

At the default 18% relative-lift assumption, the model produces roughly:

- +533 incremental repeat buyers
- +295M source units of second-order value

These are scenario outputs, not predicted or causal impacts.

## 14. Referral

Referral cannot be retrospectively measured from the available schema.

A real implementation should add at least:

- `invite_sent`
- `invite_opened`
- `invite_accepted`
- `referrer_customer_id`
- `referred_customer_id`
- `referred_signup`
- `referred_first_order`

Only then should the team calculate referral conversion, referred-buyer retention, or viral coefficient/K-factor.

## 15. Acquisition attribution limitation

The clickstream exposes only `MOBILE` and `WEB` traffic source values. Those are closer to platform/device channel than true marketing acquisition source.

Without campaign spend and referrer data, the project does **not** calculate CAC, ROAS, LTV:CAC, or incremental acquisition lift.

## 16. Privacy and repository policy

The customer source table contains direct personal fields such as names and email addresses. None of those are published in this repository or dashboard. The committed analytical outputs are aggregate-level only.

## 17. Why this methodology matters

The project deliberately avoids three common portfolio mistakes:

1. calling a public dataset "Myntra data";
2. calling an observational promo correlation causal;
3. fabricating referral or retention metrics that the schema cannot support.

The analytical goal is not to produce the most dramatic number. It is to produce a number that can survive questioning.
