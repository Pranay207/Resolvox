import argparse,json
from src.evals import evaluate
if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--limit',type=int); p.add_argument('--live',action='store_true'); a=p.parse_args()
    print(json.dumps(evaluate(1,a.limit,offline=not a.live),indent=2))
