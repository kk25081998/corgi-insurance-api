#!/usr/bin/env python3
# Generates ~20k synthetic policies deterministically for simulation.
import csv, os, random
from datetime import datetime, timedelta
random.seed(2025)

US = ["AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","IA","ID","IL","IN","KS","KY","LA","MA","MD","ME","MI","MN","MO","MS","MT","NC","ND","NE","NH","NJ","NM","NV","NY","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VA","VT","WA","WI","WV","WY"]
CATS = ["general","electronics","electronics_high_value","apparel","jewelry_high_value"]
DEST = ["low","medium","high"]
SVC  = ["ground","expedited","overnight"]
JOBS = ["full_time","part_time","seasonal_temp","contractor"]

def dminus(n): return (datetime.utcnow() - timedelta(days=n)).date().isoformat()

def sample_shipping():
    val = round(random.lognormvariate(6.4, 0.55), 2)    # ~600 avg
    cat = random.choices(CATS, weights=[0.45,0.25,0.05,0.2,0.05])[0]
    st  = random.choice(US)
    dr  = random.choices(DEST, weights=[0.55,0.35,0.10])[0]
    sv  = random.choices(SVC,  weights=[0.7,0.2,0.1])[0]
    return val, cat, st, dr, sv

def sample_ppi():
    ov  = round(random.lognormvariate(6.0, 0.5), 2)     # ~403 avg
    tm  = random.choices([3,6,9,12,18,24], weights=[0.1,0.25,0.2,0.25,0.12,0.08])[0]
    age = random.randint(18, 65)
    ten = random.choices([3,6,12,24,36], weights=[0.2,0.25,0.25,0.2,0.1])[0]
    job = random.choice(JOBS)
    st  = random.choice(US)
    return ov, tm, age, ten, job, st

def score_band_mult(product, feat):
    if product=="shipping":
        val, _, _, dr, sv = feat
        s = 0.02*(val/1000) + (0 if dr=="low" else 0.5 if dr=="medium" else 1.0) + (0.2 if sv=="ground" else 0.1 if sv=="expedited" else 0)
    else:
        ov, tm, age, ten, *_ = feat
        s = 0.02*(ov/100) + 0.1*(tm/6) + (0.3 if age<25 else 0) + (0.3 if ten<6 else 0)
    if   s<0.4: return "A", 0.90
    elif s<0.8: return "B", 1.00
    elif s<1.2: return "C", 1.10
    elif s<1.6: return "D", 1.25
    else:       return "E", 1.40

def main(n=20000):
    os.makedirs("data", exist_ok=True)
    with open("data/policies.csv","w",newline="") as f:
        w=csv.writer(f)
        w.writerow(["policy_id","product_code","partner_id","risk_band","risk_multiplier","declared_value","item_category","destination_state","destination_risk","service_level","order_value","term_months","age","tenure_months","job_category","state","effective_date","expiration_date"])
        for i in range(n):
            partner = random.choice(["ptnr_klarity","ptnr_afterday"])
            eff = dminus(random.randint(1,90))
            exp = (datetime.fromisoformat(eff)+timedelta(days=30*random.choice([1,3,6,12]))).date().isoformat()
            if random.random()<0.55:
                prod="shipping"; s=sample_shipping(); band,m=score_band_mult(prod,s)
                w.writerow([f"pol_{i}",prod,partner,band,m, s[0],s[1],s[2],s[3],s[4], "", "", "", "", "", "", eff, exp])
            else:
                prod="ppi"; p=sample_ppi(); band,m=score_band_mult(prod,p)
                w.writerow([f"pol_{i}",prod,partner,band,m, "", "", "", "", "", p[0],p[1],p[2],p[3],p[4],p[5], eff, exp])
    print("Wrote data/policies.csv")

if __name__=="__main__": main()
