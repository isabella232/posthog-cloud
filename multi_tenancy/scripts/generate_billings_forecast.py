from calendar import monthrange
import datetime
import stripe

STRIPE_API_KEY = None
if not STRIPE_API_KEY:
    raise AssertionError("You need to define STRIPE_API_KEY in this file before running the script.")

stripe.api_key = STRIPE_API_KEY

ENTERPRISE = "PostHog Enterprise"
STANDARD = "PostHog Standard"
STARTER = "PostHog Starter Plan"
PRODUCTS_TO_FORECAST = [STANDARD]
CLOUD_PRODUCTS = [STARTER, STANDARD]

NUM_FREE_EVENTS_CLOUD = 1000000
COST_PER_EVENT_CLOUD = 0.000225


def get_forecast_multiplier():
    today = datetime.datetime.today()
    days_in_month = monthrange(today.year, today.month)[-1]

    return days_in_month / today.day


def generate_forecast():
    invoices_by_customer = {}

    has_more = True
    last_seen_sub_id = None
    while has_more:
        active_subscriptions = stripe.Subscription.list(limit=100, starting_after=last_seen_sub_id)
        has_more = active_subscriptions.get("has_more")

        for sub in active_subscriptions:
            last_seen_sub_id = sub.get("id")
            upcoming_invoice = stripe.Invoice.upcoming(subscription=sub['id'])
            customer_email = upcoming_invoice.get('customer_email')
            invoices_by_customer.setdefault(customer_email, {})

            lines = upcoming_invoice['lines']['data']

            for line in lines:
                quantity = line.get('quantity')
                amount = line.get('amount')

                price_obj = line.get('price')
                product = stripe.Product.retrieve(price_obj.get('product'))

                product_name = product.get("name")

                invoices_by_customer.setdefault(customer_email, {})
                invoices_by_customer[customer_email].setdefault(product_name, {
                    "quantity": 0,
                    "amount": 0.0,
                    "discount": 0.0})
                current_invoice = invoices_by_customer[customer_email][product_name]
                current_invoice['quantity'] += quantity
                current_invoice['amount'] += amount / 100.0

                discount_amounts = line.get("discount_amounts", [])
                for discount in discount_amounts:
                    current_invoice['discount'] += (discount.get("amount", 0.0) / 100)

    cloud_billings = 0.0
    forecasted_cloud_billings = 0.0
    enterprise_billings = 0.0

    for email, invoices_by_product in invoices_by_customer.items():
        for product, invoice in invoices_by_product.items():
            if product == STANDARD:
                forecasted_billable_quantity = max(0, (
                            invoice.get("quantity") * get_forecast_multiplier()) - NUM_FREE_EVENTS_CLOUD)
                forecasted_amount = (forecasted_billable_quantity * COST_PER_EVENT_CLOUD) - invoice.get("discount")
                invoice["forecasted"] = {"amount": forecasted_amount, "quantity": quantity}
                forecasted_cloud_billings += forecasted_amount
                cloud_billings += invoice.get("amount") - invoice.get("discount")
            elif product == STARTER:
                total = invoice.get("amount") - invoice.get("discount")
                cloud_billings += total
                forecasted_cloud_billings += total
            elif product == ENTERPRISE:
                total = invoice.get("amount") - invoice.get("discount")
                enterprise_billings += total
            else:
                raise AssertionError(f'Unsupported product type {product}')

    print(f"Cloud billings: {cloud_billings}, forecasted: {forecasted_cloud_billings}")
    print(f"Enterprise billings: {enterprise_billings}")


if __name__ == '__main__':
    generate_forecast()
