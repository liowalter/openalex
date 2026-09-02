import argparse
import requests
import time
from typing import Any, Dict, List, Optional, Set

OPENAIRE_API_BASE = "https://api.openaire.eu/graph"

def openaire_get(endpoint: str, params: Optional[Dict[str, Any]] = None, api_token: Optional[str] = None) -> Dict[str, Any]:
    if params is None:
        params = {}
    url = f"{OPENAIRE_API_BASE}/{endpoint}"
    headers = {"accept": "application/json"}
    if api_token:
        headers["Authorization"] = f"Bearer {api_token}"
    
    # Simple retry logic for rate limits or transient errors
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            if attempt == 2:
                raise
            time.sleep(1)
    return {}

def get_publication(pid: str, api_token: Optional[str] = None) -> Optional[Dict[str, Any]]:
    # Search for publication by PID (e.g. DOI)
    data = openaire_get("v2/researchProducts", {"pid": pid}, api_token=api_token)
    results = data.get("results", [])
    if results:
        return results[0]
    return None

def get_author_works(author_name: Optional[str] = None, orcid: Optional[str] = None, api_token: Optional[str] = None) -> List[Dict[str, Any]]:
    works = []
    page = 1
    page_size = 50
    
    params = {
        "pageSize": page_size,
        "type": "publication"
    }
    
    if orcid:
        params["authorOrcid"] = orcid
    elif author_name:
        # OpenAIRE's authorFullName search is a bit loose. 
        # We search by name but we'll add a check in the results to match the author name more strictly.
        # We remove commas as they might cause issues in some API implementations
        search_name = author_name.replace(",", "")
        # If the name is in "Surname, Name" format, removing comma makes it "Surname Name"
        # OpenAIRE seems to handle "Name Surname" or "Surname Name"
        params["authorFullName"] = search_name
    else:
        return []

    while True:
        params["page"] = page
        data = openaire_get("v2/researchProducts", params, api_token=api_token)
        results = data.get("results", [])
        
        # Strict filtering to avoid "too many results" if author name is common or search is too broad
        filtered_results = []
        for work in results:
            work_authors = [a.get("fullName", "").lower() for a in (work.get("authors") or [])]
            # Match if the requested author is actually in the list (or at least one of the PIDs matches)
            if orcid:
                match = False
                for wa in (work.get("authors") or []):
                    if wa.get("pid") and isinstance(wa["pid"], list):
                        for pid_obj in wa["pid"]:
                            if pid_obj.get("scheme") == "orcid" and pid_obj.get("value") == orcid:
                                match = True
                                break
                    if match: break
                if match:
                    filtered_results.append(work)
            elif author_name:
                # Basic normalization for name check
                norm_target = author_name.lower().replace(",", "").replace(".", "").strip()
                match = False
                for wa_name in work_authors:
                    norm_wa = wa_name.lower().replace(",", "").replace(".", "").strip()
                    if norm_target == norm_wa or norm_target in norm_wa or norm_wa in norm_target:
                        match = True
                        break
                if match:
                    filtered_results.append(work)
            else:
                filtered_results.append(work)

        works.extend(filtered_results)
        
        num_found = data.get("header", {}).get("numFound", 0)
        # If we got no filtered results from a page but there are more pages, 
        # it's possible the author is on later pages or not at all.
        # However, to be safe and avoid 1000s of requests, we stop if we have enough or if results are empty.
        if not results or len(works) >= 1000: # Safety cap
            break
        
        # If the number of results found by API is very large (e.g. > 500) and we are searching by name,
        # it's likely a broad search that's not yielding what we want efficiently.
        if author_name and not orcid and num_found > 1000 and page > 5:
             break

        if len(works) >= num_found or len(results) < page_size:
            break

        page += 1
    
    return works

def get_organization_country(org_id: str, cache: Dict[str, str], api_token: Optional[str] = None) -> Optional[str]:
    if org_id in cache:
        return cache[org_id]
    
    try:
        data = openaire_get("v1/organizations", {"id": org_id}, api_token=api_token)
        results = data.get("results", [])
        if results:
            country_code = results[0].get("country", {}).get("code")
            if country_code:
                cache[org_id] = country_code
                return country_code
    except Exception:
        pass
    
    cache[org_id] = None
    return None

def is_swiss_work(work: Dict[str, Any], org_country_cache: Dict[str, str], api_token: Optional[str] = None) -> bool:
    # Check if work has direct country info
    countries = (work.get("countries") or [])
    if countries:
        for c in countries:
            if isinstance(c, dict) and c.get("code") == "CH":
                return True
            if c == "CH":
                return True
    
    # Check associated organizations
    orgs = work.get("organizations") or []
    if not isinstance(orgs, list):
        orgs = [orgs] if orgs else []
        
    for org in orgs:
        if not org: continue
        org_id = org.get("id")
        if org_id:
            country = get_organization_country(org_id, org_country_cache, api_token=api_token)
            if country == "CH":
                return True
    
    return False

def get_swiss_coauthors(work: Dict[str, Any], org_country_cache: Dict[str, str], api_token: Optional[str] = None) -> List[Dict[str, Any]]:
    # OpenAIRE currently doesn't link authors to specific organizations in the researchProduct record
    # So if the work is Swiss-affiliated, we consider all co-authors as potentially Swiss
    # or we check if the work HAS Swiss affiliation and then list co-authors.
    # To be more precise, if the work has Swiss affiliation, we'll mark all its authors.
    
    if not is_swiss_work(work, org_country_cache, api_token=api_token):
        return []
    
    swiss_coauthors = []
    authors = work.get("authorships", work.get("authors", []))
    if not isinstance(authors, list):
        authors = [authors] if authors else []
        
    for auth in authors:
        name = auth.get("fullName") or f"{auth.get('name', '')} {auth.get('surname', '')}".strip()
        if not name:
            continue
            
        author_id = None
        pids = auth.get("pid") or []
        if not isinstance(pids, list):
            pids = [pids]
            
        for pid_obj in pids:
            if isinstance(pid_obj, dict):
                pid_id = pid_obj.get("id")
                if isinstance(pid_id, dict) and pid_id.get("scheme") == "orcid":
                    author_id = pid_id.get("value")
        
        # If we can't get an ID, we use the name as ID (less ideal but necessary)
        swiss_coauthors.append({
            "id": author_id or name,
            "name": name,
            "orcid": author_id if author_id and "0000-" in author_id else None
        })
    return swiss_coauthors

def main():
    parser = argparse.ArgumentParser(description="Check for Swiss co-authors using OpenAIRE API.")
    parser.add_argument("--doi", default="10.7589/2019-08-202", help="DOI of the starting publication.")
    parser.add_argument("--api-token", help="OpenAIRE Personal Access Token.")
    
    args = parser.parse_args()
    
    print(f"Fetching starting publication: {args.doi}...")
    start_work = get_publication(args.doi, api_token=args.api_token)
    
    if not start_work:
        print(f"Could not find publication with DOI: {args.doi}")
        return
    
    title = start_work.get("mainTitle")
    print(f"Title: {title}")
    
    authors = start_work.get("authors", [])
    print(f"Found {len(authors)} authors.")
    
    # cache for organization countries to avoid redundant API calls
    org_country_cache = {}
    
    # swiss_coauthors_stats structure:
    # { author_key: { "name": name, "orcid": orcid, "works": set(), 
    #                 "links": { original_author_name: { "works_count": 0, "topics": set() } } } }
    stats = {}
    
    for orig_author in authors:
        name = orig_author.get("fullName")
        orcid = None
        pids = orig_author.get("pid") or []
        if not isinstance(pids, list):
            pids = [pids]
            
        for pid_item in pids:
            if isinstance(pid_item, dict):
                pid_id = pid_item.get("id")
                if isinstance(pid_id, dict) and pid_id.get("scheme") == "orcid":
                    orcid = pid_id.get("value")
        
        print(f"\nChecking original author: {name} (ORCID: {orcid or 'N/A'})")
        
        # Fetch works
        works = get_author_works(author_name=name, orcid=orcid, api_token=args.api_token)
        print(f"  Found {len(works)} publications.")
        
        for work in works:
            # Skip the starting work
            work_pids = [p.get("value") for p in (work.get("pids") or [])]
            if args.doi in work_pids:
                continue
            
            # Check if work has Swiss affiliation
            if is_swiss_work(work, org_country_cache, api_token=args.api_token):
                # Get topics/subjects
                work_topics = []
                for subject_obj in (work.get("subjects") or []):
                    subj = subject_obj.get("subject", {})
                    if subj.get("scheme") == "FOS" or subj.get("scheme") == "keyword":
                        work_topics.append(subj.get("value"))

                # Get all co-authors of this Swiss work
                coauthors = get_swiss_coauthors(work, org_country_cache, api_token=args.api_token)
                for ca in coauthors:
                    ca_id = ca["id"]
                    if ca_id not in stats:
                        stats[ca_id] = {
                            "name": ca["name"],
                            "orcid": ca["orcid"],
                            "works": set(),
                            "links": {}
                        }
                    
                    stats[ca_id]["works"].add(work.get("id"))
                    
                    if name not in stats[ca_id]["links"]:
                        stats[ca_id]["links"][name] = {
                            "works_count": 0,
                            "topics": set()
                        }
                    
                    stats[ca_id]["links"][name]["works_count"] += 1
                    stats[ca_id]["links"][name]["topics"].update(work_topics)

    if stats:
        print("\n" + "="*120)
        print("SWISS CO-AUTHORS SUMMARY (OpenAIRE)")
        print("="*120)
        print(f"{'Swiss Author':<25} | {'Total':<5} | {'Original Author':<25} | {'Co-Works':<8} | {'Topics'}")
        print("-" * 150)
        
        sorted_keys = sorted(stats.keys(), key=lambda k: len(stats[k]["works"]), reverse=True)
        
        for key in sorted_keys:
            sa = stats[key]
            first_row = True
            sorted_links = sorted(sa["links"].items(), key=lambda x: x[1]["works_count"], reverse=True)
            
            for orig_name, link_data in sorted_links:
                co_works = link_data["works_count"]
                topics = ", ".join(sorted(list(link_data["topics"]))[:5]) # Limit topics
                
                name_col = sa["name"][:25] if first_row else ""
                total_col = str(len(sa["works"])) if first_row else ""
                
                print(f"{name_col:<25} | {total_col:<5} | {orig_name[:25]:<25} | {co_works:<8} | {topics}")
                first_row = False
            print("-" * 150)
    else:
        print("\nNo Swiss co-authors found.")

if __name__ == "__main__":
    main()
