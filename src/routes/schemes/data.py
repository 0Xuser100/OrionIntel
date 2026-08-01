from typing import Optional

from pydantic import BaseModel


class ProcessRequest(BaseModel):
    # the asset_name returned by /upload; None -> process every file in the project
    file_id: Optional[str] = None
    chunk_size: Optional[int] = 100
    overlap_size: Optional[int] = 20
    do_reset: Optional[int] = 0
