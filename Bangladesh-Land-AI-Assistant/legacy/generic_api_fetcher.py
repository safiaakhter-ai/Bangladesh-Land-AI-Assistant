"""
Generic REST API Data Collector
A reusable Python template for fetching, paginating, and saving JSON data from standard REST APIs.
"""

import requests
import json
import time
import os

class GenericAPIFetcher:
    def __init__(self, base_url, headers=None, rate_limit_delay=0.5):
        """
        Initialize the API fetcher.
        
        :param base_url: Base URL of the target API endpoint.
        :param headers: Optional dictionary of HTTP headers (e.g., Authorization, User-Agent).
        :param rate_limit_delay: Pause in seconds between consecutive requests.
        """
        self.base_url = base_url
        self.headers = headers or {"User-Agent": "GenericAPIFetcher/1.0"}
        self.rate_limit_delay = rate_limit_delay

    def fetch_endpoint(self, endpoint_path="", params=None):
        """
        Fetch data from a single endpoint path.
        """
        url = f"{self.base_url.rstrip('/')}/{endpoint_path.lstrip('/')}"
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=10)
            response.raise_for_status()
            
            # Rate limiting delay
            time.sleep(self.rate_limit_delay)
            
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err} for URL: {url}")
        except requests.exceptions.RequestException as err:
            print(f"Request error occurred: {err} for URL: {url}")
        return None

    def fetch_paginated(self, endpoint_path="", page_param="page", start_page=1, max_pages=10):
        """
        Fetch paginated data sequentially across multiple pages.
        """
        all_results = []
        current_page = start_page

        while current_page <= start_page + max_pages - 1:
            print(f"Fetching page {current_page}...")
            params = {page_param: current_page}
            data = self.fetch_endpoint(endpoint_path, params=params)
            
            if not data:
                print("No more data received or an error occurred. Stopping.")
                break
                
            # Assume data is either a list or contains a list in a field like 'data' or 'results'
            items = []
            if isinstance(data, list):
                items = data
            elif isinstance(data, dict):
                items = data.get("data") or data.get("results") or [data]

            if not items:
                print("Empty page reached. Pagination complete.")
                break

            all_results.extend(items)
            current_page += 1

        return all_results

    def save_to_json(self, data, output_filename="api_output.json", append=True, deduplicate=True):
        """
        Save collected data list or dictionary to a JSON file.
        If append=True and the file already exists, new data is appended/merged with previous data.
        """
        output_dir = os.path.dirname(output_filename)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        final_data = data

        if append and os.path.exists(output_filename):
            try:
                with open(output_filename, "r", encoding="utf-8") as f:
                    existing_data = json.load(f)

                # Determine list containers
                existing_is_dict_data = isinstance(existing_data, dict) and isinstance(existing_data.get("data"), list)
                new_is_dict_data = isinstance(data, dict) and isinstance(data.get("data"), list)

                existing_list = existing_data["data"] if existing_is_dict_data else (existing_data if isinstance(existing_data, list) else None)
                new_list = data["data"] if new_is_dict_data else (data if isinstance(data, list) else None)

                if existing_list is not None and new_list is not None:
                    # Merge lists
                    merged_list = list(existing_list)
                    
                    if deduplicate:
                        def get_item_key(item):
                            if isinstance(item, dict):
                                for id_key in ("ID", "id", "code", "BBS_CODE", "uuid"):
                                    if id_key in item:
                                        return (id_key, item[id_key])
                                try:
                                    return json.dumps(item, sort_keys=True)
                                except TypeError:
                                    return str(item)
                            return item

                        seen_keys = {get_item_key(item) for item in existing_list}
                        for item in new_list:
                            key = get_item_key(item)
                            if key not in seen_keys:
                                seen_keys.add(key)
                                merged_list.append(item)
                    else:
                        merged_list.extend(new_list)

                    if existing_is_dict_data:
                        existing_data["data"] = merged_list
                        final_data = existing_data
                    elif new_is_dict_data:
                        data["data"] = merged_list
                        final_data = data
                    else:
                        final_data = merged_list

                elif isinstance(existing_data, dict) and isinstance(data, dict):
                    existing_data.update(data)
                    final_data = existing_data

            except Exception as e:
                print(f"Warning: Could not read existing file for appending ({e}). Overwriting file.")
                final_data = data

        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(final_data, f, indent=2, ensure_ascii=False)

        count = 0
        if isinstance(final_data, list):
            count = len(final_data)
        elif isinstance(final_data, dict) and isinstance(final_data.get("data"), list):
            count = len(final_data["data"])
        else:
            count = 1

        print(f"[OK] Saved total of {count} items to {output_filename}")

    def fetch_all_upazilas_from_posts(self, posts_file="data/posts.json", output_folder="data/upazilas", combined_file="data/upazilas/all_upazilas.json"):
        """
        Reads district records from posts_file, extracts each BBS_CODE,
        fetches upazilas endpoint for each district, and saves results into output_folder.
        """
        if not os.path.exists(posts_file):
            print(f"Error: {posts_file} not found.")
            return

        with open(posts_file, "r", encoding="utf-8") as f:
            posts_data = json.load(f)

        districts = posts_data.get("data", []) if isinstance(posts_data, dict) else posts_data
        if not isinstance(districts, list):
            print("Error: Could not parse list of districts from posts file.")
            return

        print(f"Found {len(districts)} district records in {posts_file}.")
        os.makedirs(output_folder, exist_ok=True)

        total_upazilas_collected = 0

        for idx, district in enumerate(districts, start=1):
            bbs_code = district.get("BBS_CODE")
            district_name = district.get("NAME_EN") or district.get("NAME") or f"District {bbs_code}"

            if not bbs_code:
                print(f"[{idx}/{len(districts)}] Skipping district without BBS_CODE: {district_name}")
                continue

            print(f"[{idx}/{len(districts)}] Fetching upazilas for {district_name} (BBS_CODE: {bbs_code})...")
            endpoint = f"/upazilas?DISTRICT_BBS_CODE={bbs_code}"
            upazila_data = self.fetch_endpoint(endpoint)

            if upazila_data:
                # Save individual file per district in output_folder
                dist_filename = os.path.join(output_folder, f"upazilas_{bbs_code}.json")
                with open(dist_filename, "w", encoding="utf-8") as df:
                    json.dump(upazila_data, df, indent=2, ensure_ascii=False)

                # Also aggregate into combined file inside output_folder
                self.save_to_json(upazila_data, combined_file, append=True, deduplicate=True)

                items = upazila_data.get("data", []) if isinstance(upazila_data, dict) else upazila_data
                count = len(items) if isinstance(items, list) else 1
                total_upazilas_collected += count
                print(f"  -> Got {count} upazilas.")
            else:
                print(f"  -> Failed to fetch data for BBS_CODE {bbs_code}")

        print(f"\n[DONE] Collected total of {total_upazilas_collected} upazilas across {len(districts)} districts.")
        print(f"Individual district files saved in: {output_folder}/")
        print(f"Combined data saved in: {combined_file}")

    def fetch_all_mouzas_from_upazilas(
        self,
        upazilas_file="data/upazilas/all_upazilas.json",
        output_folder="data/mouzas",
        combined_file="data/mouzas/all_mouzas.json",
        survey_ids=(1, 2, 3, 7),
        skip_existing=True
    ):
        """
        Reads upazilas from upazilas_file, extracts DISTRICT_BBS_CODE and UPAZILA_BBS_CODE (from BBS_CODE),
        queries /mouzas endpoint for each SURVEY_ID in survey_ids, and saves results into output_folder.
        """
        if not os.path.exists(upazilas_file):
            print(f"Error: {upazilas_file} not found.")
            return

        with open(upazilas_file, "r", encoding="utf-8") as f:
            upazila_content = json.load(f)

        upazilas = upazila_content.get("data", []) if isinstance(upazila_content, dict) else upazila_content
        if not isinstance(upazilas, list):
            print("Error: Could not parse list of upazilas from file.")
            return

        print(f"Found {len(upazilas)} upazilas in {upazilas_file}.")
        os.makedirs(output_folder, exist_ok=True)

        total_requests = len(upazilas) * len(survey_ids)
        request_count = 0
        total_mouzas_collected = 0

        for idx, upz in enumerate(upazilas, start=1):
            dist_bbs = upz.get("DISTRICT_BBS_CODE")
            upz_bbs = upz.get("BBS_CODE")
            upz_name = upz.get("NAME_EN") or upz.get("NAME") or f"Upazila {upz_bbs}"
            dist_name = upz.get("DISTRICT_NAME_EN") or upz.get("DISTRICT_NAME") or f"District {dist_bbs}"

            if not dist_bbs or not upz_bbs:
                print(f"[{idx}/{len(upazilas)}] Skipping invalid upazila record: {upz_name}")
                continue

            for survey_id in survey_ids:
                request_count += 1
                individual_file = os.path.join(output_folder, f"mouzas_dist_{dist_bbs}_upz_{upz_bbs}_survey_{survey_id}.json")

                if skip_existing and os.path.exists(individual_file):
                    try:
                        with open(individual_file, "r", encoding="utf-8") as sf:
                            sf_data = json.load(sf)
                        items = sf_data.get("data", []) if isinstance(sf_data, dict) else sf_data
                        cnt = len(items) if isinstance(items, list) else 0
                        total_mouzas_collected += cnt
                        print(f"[{request_count}/{total_requests}] (Cached) {dist_name} -> {upz_name} (Survey {survey_id}): {cnt} mouzas")
                        continue
                    except Exception:
                        pass

                endpoint = f"/mouzas?DISTRICT_BBS_CODE={dist_bbs}&UPAZILA_BBS_CODE={upz_bbs}&SURVEY_ID={survey_id}"
                mouza_data = self.fetch_endpoint(endpoint)

                if mouza_data:
                    items = mouza_data.get("data", []) if isinstance(mouza_data, dict) else mouza_data
                    cnt = len(items) if isinstance(items, list) else (1 if items else 0)

                    # Save individual JSON file per query
                    with open(individual_file, "w", encoding="utf-8") as f_out:
                        json.dump(mouza_data, f_out, indent=2, ensure_ascii=False)

                    if cnt > 0:
                        # Append non-empty results to combined_file
                        self.save_to_json(mouza_data, combined_file, append=True, deduplicate=True)
                        total_mouzas_collected += cnt
                        print(f"[{request_count}/{total_requests}] {dist_name} -> {upz_name} (Survey {survey_id}): Got {cnt} mouzas!")
                    else:
                        print(f"[{request_count}/{total_requests}] {dist_name} -> {upz_name} (Survey {survey_id}): 0 mouzas.")
                else:
                    print(f"[{request_count}/{total_requests}] Failed request for {dist_name} -> {upz_name} (Survey {survey_id})")

        print(f"\n[DONE] Finished fetching mouzas. Collected total of {total_mouzas_collected} mouzas.")
        print(f"Individual files saved in: {output_folder}/")
        print(f"Combined dataset saved in: {combined_file}")


def main():
    EXAMPLE_BASE_URL = "https://dlrms-final-api.onrender.com/api"
    
    fetcher = GenericAPIFetcher(base_url=EXAMPLE_BASE_URL, rate_limit_delay=0.1)
    
    print("=== Fetching Mouzas for All Upazilas and Survey IDs (1, 2, 3, 7) ===")
    fetcher.fetch_all_mouzas_from_upazilas(
        upazilas_file="data/upazilas/all_upazilas.json",
        output_folder="data/mouzas",
        combined_file="data/mouzas/all_mouzas.json",
        survey_ids=(1, 2, 3, 7)
    )


if __name__ == "__main__":
    main()
