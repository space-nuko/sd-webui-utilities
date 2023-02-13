import os
import os.path
import sys
import bisect
import shutil
import safetensors_hack
import tqdm
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker

from db_models import Base, LoRAModel


DATABASE_NAME = os.getenv("DATABASE_NAME", "lora_db")
engine = create_engine(f"sqlite:///{DATABASE_NAME}.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)


results = []


stmt = select(LoRAModel)
with Session() as session:
    for row in session.execute(stmt):
        model = row[0]
        bn = os.path.splitext(os.path.basename(model.filename))[0]
        if model.model_hash:
            bn += f"({model.model_hash[0:12]})"

        if model.tags:
            tags = [t.strip().lower() for t in model.tags.split(",")]
            if "style" in tags or "art style" in tags:
                results.append(bn)
                continue

        if bn.startswith("st-") or bn.startswith("artist-"):
            results.append(bn)

print("\n".join(results))
