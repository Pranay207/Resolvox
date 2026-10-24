"""Call unchanged organizer tools; trace only allowlisted values, never proof."""
import importlib.util
from .config import dataset_dir
from .normalize import redact
SAFE_ORDER={'order_id','status','placed_at','promised_date','shipped_on','delivered_on','payment_method','delivery_type','delivery_attempts','is_plus','items','total_inr','subtotal_inr','coupon_code','coupon_discount_inr','coupon_min_order_inr','delivery_fee_inr','cod_fee_inr','contacts_last_7_days','return_sku','return_line_no','return_qty','return_reason','return_status','return_requested_on','return_pickup_on','return_qc_passed_on','return_refund_initiated_on','return_refund_method','return_refund_amount_inr','return_refund_completed_on','return_rrn','return_reverse_pickup_fee_inr','cancellation_refund_initiated_on','cancellation_refund_method','cancellation_refund_amount_inr','cancellation_rrn','rto_refund_initiated_on','rto_refund_method','rto_refund_amount_inr','rto_rrn','damage_sku','damage_issue','damage_reported_at','damage_hours_after_delivery','damage_photos_attached','damage_status','express_late_credit_inr','express_late_credit_on'}
class Tools:
    def __init__(self):
        spec=importlib.util.spec_from_file_location('zentromart_organizer_tools',dataset_dir()/'tools/tools.py')
        self.module=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.module)
    def lookup(self,oid:str,proof:str|None=None) -> tuple[dict,dict]:
        raw=self.module.lookup_order(oid,verification_value=proof)
        safe={k:v for k,v in raw.items() if k in SAFE_ORDER} if raw.get('verified') else {}
        trace={'name':'lookup_order','arguments':{'order_id':oid},'result':{'verified':bool(raw.get('verified')),'verification_required':not bool(raw.get('verified'))}}
        if proof is not None: trace['arguments']['verification_value']='[REDACTED]'
        if raw.get('verified'): trace['result'].update({'found':True,'order':safe})
        return safe,trace
    def ticket(self,summary:str,oid:str|None,reason:str,intent:str) -> tuple[dict,dict]:
        summary=redact(summary)
        result=self.module.create_ticket(summary=summary,order_id=oid,reason=reason,intent=intent)
        safe={k:result[k] for k in ['created','ticket_id'] if k in result}
        return safe,{'name':'create_ticket','arguments':{'summary':summary,'order_id':oid,'reason':reason,'intent':intent},'result':safe}
