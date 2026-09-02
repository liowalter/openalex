import argparse
import requests
from typing import Any, Dict, List, Optional

OPENALEX_BASE_URL = "https://api.openalex.org"

def openalex_get(endpoint: str, params: Optional[Dict[str, Any]] = None, api_key: Optional[str] = None) -> Dict[str, Any]:
    if params is None:
        params = {}
    request_params = dict(params)
    if api_key:
        request_params["api_key"] = api_key

    url = f"{OPENALEX_BASE_URL}/{endpoint}"
    response = requests.get(url, params=request_params, timeout=30)
    response.raise_for_status()
    return response.json()

def get_work(work_id: str, api_key: Optional[str] = None) -> Dict[str, Any]:
    # Ensure ID is just the ID part if a full URL is provided
    if work_id.startswith("https://openalex.org/"):
        work_id = work_id.split("/")[-1]
    return openalex_get(f"works/{work_id}", api_key=api_key)

def get_author_works(author_id: str, mailto: Optional[str] = None, api_key: Optional[str] = None) -> List[Dict[str, Any]]:
    works = []
    cursor = "*"
    
    # We might want to limit the number of works per author to avoid massive downloads
    # but for completeness we'll try to get them all or a reasonable amount.
    while True:
        params = {
            "filter": f"author.id:{author_id}",
            "per-page": 200,
            "cursor": cursor,
        }
        if mailto:
            params["mailto"] = mailto
        
        data = openalex_get("works", params, api_key=api_key)
        results = data.get("results", [])
        works.extend(results)
        
        next_cursor = data.get("meta", {}).get("next_cursor")
        if not results or not next_cursor:
            break
        cursor = next_cursor
        
        # Safety break to avoid infinite loops or too many requests
        if len(works) > 1000:
            break
            
    return works

def has_swiss_affiliation(work: Dict[str, Any]) -> bool:
    for authorship in work.get("authorships", []):
        for inst in authorship.get("institutions", []):
            if inst.get("country_code") == "CH":
                return True
        # Some older or less complete data might have country_code in countries list
        if "CH" in authorship.get("countries", []):
            return True
    return False

def main():
    parser = argparse.ArgumentParser(description="Check for Swiss co-authors of authors of a given publication.")
    parser.add_argument("--work-id", default="W3146729407", help="OpenAlex ID of the starting publication.")
    parser.add_argument("--mailto", help="Contact email for OpenAlex polite pool.")
    parser.add_argument("--api-key", help="OpenAlex API key.")
    
    args = parser.parse_args()
    
    print(f"Fetching starting work: {args.work_id}...")
    try:
        start_work = get_work(args.work_id, api_key=args.api_key)
    except Exception as e:
        print(f"Error fetching work {args.work_id}: {e}")
        return

    authorships = start_work.get("authorships", [])
    original_author_ids = {a.get("author", {}).get("id") for a in authorships if a.get("author", {}).get("id")}
    print(f"Found {len(authorships)} authors in the starting work.")

    # Dictionary to store Swiss co-author info:
    # { author_id: { "name": name, "affiliations": set(), "works": set(), 
    #                "links": { original_author_name: { "works_count": 0, "topics": set() } } } }
    swiss_coauthors_stats = {}

    for authorship in authorships:
        author = authorship.get("author", {})
        author_id = author.get("id")
        author_name = author.get("display_name")
        
        if not author_id:
            continue
            
        print(f"\nChecking original author: {author_name} ({author_id})")
        
        # Get all works for this author
        works = get_author_works(author_id, mailto=args.mailto, api_key=args.api_key)
        print(f"  Found {len(works)} publications for this author.")
        
        for work in works:
            if work.get("id") == start_work.get("id"):
                continue
            
            # Check if this work has any Swiss affiliation
            # And also collect all Swiss authors from it
            work_has_swiss = False
            current_work_swiss_authors = []
            
            for auth in work.get("authorships", []):
                is_swiss = False
                author_insts = []
                for inst in auth.get("institutions", []):
                    author_insts.append(inst.get("display_name"))
                    if inst.get("country_code") == "CH":
                        is_swiss = True
                
                if not is_swiss and "CH" in auth.get("countries", []):
                    is_swiss = True
                
                if is_swiss:
                    work_has_swiss = True
                    c_author = auth.get("author", {})
                    c_id = c_author.get("id")
                    if c_id:
                        current_work_swiss_authors.append({
                            "id": c_id,
                            "name": c_author.get("display_name"),
                            "affiliations": author_insts
                        })
            
            if work_has_swiss:
                # Collect topics from the work
                work_topics = []
                for topic_obj in work.get("topics", []):
                    topic_name = topic_obj.get("display_name")
                    if topic_name:
                        work_topics.append(topic_name)

                for sa in current_work_swiss_authors:
                    sid = sa["id"]
                    if sid not in swiss_coauthors_stats:
                        swiss_coauthors_stats[sid] = {
                            "name": sa["name"],
                            "affiliations": set(),
                            "works": set(),
                            "links": {}  # name -> {count, topics}
                        }
                    swiss_coauthors_stats[sid]["affiliations"].update(sa["affiliations"])
                    swiss_coauthors_stats[sid]["works"].add(work.get("id"))
                    
                    if author_name not in swiss_coauthors_stats[sid]["links"]:
                        swiss_coauthors_stats[sid]["links"][author_name] = {
                            "works_count": 0,
                            "topics": set()
                        }
                    
                    # We increment the count for this specific original-swiss pair
                    # but only if we haven't seen this work for this specific pair yet?
                    # The outer loop is original authors. The middle is works of that author.
                    # So we are looking at Work W of Original Author O. 
                    # If Swiss Author S is also in Work W, then (O, S) have co-authored Work W.
                    # Since we iterate over works of O, each work is processed once for O.
                    swiss_coauthors_stats[sid]["links"][author_name]["works_count"] += 1
                    swiss_coauthors_stats[sid]["links"][author_name]["topics"].update(work_topics)

    if swiss_coauthors_stats:
        print("\n" + "="*100)
        print("SWISS CO-AUTHORS SUMMARY")
        print("="*100)
        print(f"{'Swiss Author':<25} | {'Total':<5} | {'Original Author':<25} | {'Co-Works':<8} | {'Topics'}")
        print("-" * 140)
        
        # Sort Swiss authors by total count descending
        sorted_swiss_ids = sorted(
            swiss_coauthors_stats.keys(), 
            key=lambda sid: len(swiss_coauthors_stats[sid]["works"]), 
            reverse=True
        )
        
        for sid in sorted_swiss_ids:
            sa = swiss_coauthors_stats[sid]
            swiss_name = sa["name"]
            total_works = len(sa["works"])
            
            # For each Swiss author, show their links to original authors
            first_row = True
            sorted_links = sorted(sa["links"].items(), key=lambda x: x[1]["works_count"], reverse=True)
            
            for orig_name, link_data in sorted_links:
                co_works = link_data["works_count"]
                topics = ", ".join(sorted(link_data["topics"]))
                
                name_col = swiss_name[:25] if first_row else ""
                total_col = str(total_works) if first_row else ""
                
                print(f"{name_col:<25} | {total_col:<5} | {orig_name[:25]:<25} | {co_works:<8} | {topics}")
                first_row = False
            
            print("-" * 140)
    else:
        print("\nNo Swiss co-authors found in other publications.")

if __name__ == "__main__":
    main()
