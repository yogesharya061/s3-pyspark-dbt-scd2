CONTRACTS = {
 'customers': {'key':'customer_id','fields':['customer_id','name','email','city','tier','is_deleted','updated_at']},
 'orders': {'key':'order_id','fields':['order_id','customer_id','product_id','quantity','unit_price','ordered_at','updated_at']},
 'products': {'key':'product_id','fields':['product_id','product_name','category','updated_at']}
}
