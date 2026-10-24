"""Deterministic policy date arithmetic."""
from datetime import date,timedelta
from decimal import Decimal,ROUND_HALF_UP

def parse_date(value:str|None) -> date|None: return date.fromisoformat(value[:10]) if value else None

def business_add(start:date,days:int,holidays:set[str]) -> date:
    current=start; counted=0
    while counted<days:
        current+=timedelta(days=1)
        if current.weekday()!=6 and current.isoformat() not in holidays: counted+=1
    return current

def business_elapsed(start:date,end:date,holidays:set[str]) -> int:
    current=start; count=0
    while current<end:
        current+=timedelta(days=1); count+=current.weekday()!=6 and current.isoformat() not in holidays
    return count

def return_window(category:str,delivered:date|None,placed:date|None,standard:int|None) -> int|None:
    if category=='electronics' and delivered and delivered<date(2026,8,1): return 10
    if category=='fashion' and placed and date(2026,10,1)<=placed<=date(2026,10,15): return 30
    return standard

def return_deadline(delivered:date,days:int) -> date: return delivered+timedelta(days=days)

def fmt(value:date|str) -> str:
    d=parse_date(value) if isinstance(value,str) else value
    return f'{d.day} {d:%B %Y}' if d else 'not recorded'

def partial_refund(subtotal:int,item_gross:int,discount:int,minimum:int,pickup_fee:int=0) -> int:
    if subtotal<=0 or not 0<=item_gross<=subtotal: raise ValueError('Invalid order amounts')
    share=Decimal(discount)*Decimal(item_gross)/Decimal(subtotal); refund=Decimal(item_gross)-share
    if subtotal-item_gross<minimum: refund-=Decimal(discount)-share
    return max(0,int((refund-pickup_fee).quantize(Decimal('1'),rounding=ROUND_HALF_UP)))
