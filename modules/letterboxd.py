import time
from modules import util
from modules.util import Failed

logger = util.logger

builders = ["letterboxd_list", "letterboxd_list_details"]
base_url = "https://letterboxd.com"

class Letterboxd:
    def __init__(self, config):
        self.config = config

    def _parse_list(self, list_url, language):
        if self.config.trace_mode:
            logger.debug(f"URL: {list_url}")
        response = self.config.get_html(list_url, headers=util.header(language))
        letterboxd_ids = response.xpath("//li[contains(@class, 'poster-container')]/div/@data-film-id")
        items = []
        for letterboxd_id in letterboxd_ids:
            slugs = response.xpath(f"//div[@data-film-id='{letterboxd_id}']/@data-film-slug")
            items.append((letterboxd_id, slugs[0]))
        next_url = response.xpath("//a[@class='next']/@href")
        if len(next_url) > 0:
            time.sleep(2)
            items.extend(self._parse_list(f"{base_url}{next_url[0]}", language))
        return items

    def _tmdb(self, letterboxd_url, language):
        if self.config.trace_mode:
            logger.debug(f"URL: {letterboxd_url}")
        response = self.config.get_html(letterboxd_url, headers=util.header(language))
        ids = response.xpath("//a[@data-track-action='TMDb']/@href")
        if len(ids) > 0 and ids[0]:
            if "themoviedb.org/movie" in ids[0]:
                return util.regex_first_int(ids[0], "TMDb Movie ID")
            raise Failed(f"Letterboxd Error: TMDb Movie ID not found in {ids[0]}")
        raise Failed(f"Letterboxd Error: TMDb Movie ID not found at {letterboxd_url}")

    def get_list_description(self, list_url, language):
        if self.config.trace_mode:
            logger.debug(f"URL: {list_url}")
        response = self.config.get_html(list_url, headers=util.header(language))
        descriptions = response.xpath("//meta[@property='og:description']/@content")
        return descriptions[0] if len(descriptions) > 0 and len(descriptions[0]) > 0 else None

    def validate_letterboxd_lists(self, letterboxd_lists, language):
        valid_lists = []
        for letterboxd_list in util.get_list(letterboxd_lists, split=False):
            list_url = letterboxd_list.strip()
            if not list_url.startswith(base_url):
                raise Failed(f"Letterboxd Error: {list_url} must begin with: {base_url}")
            elif len(self._parse_list(list_url, language)) > 0:
                valid_lists.append(list_url)
            else:
                raise Failed(f"Letterboxd Error: {list_url} failed to parse")
        return valid_lists

    def get_tmdb_ids(self, method, data, language):
        if method == "letterboxd_list":
            logger.info(f"Processing Letterboxd List: {data}")
            items = self._parse_list(data, language)
            total_items = len(items)
            if total_items > 0:
                ids = []
                for i, item in enumerate(items, 1):
                    letterboxd_id, slug = item
                    logger.ghost(f"Finding TMDb ID {i}/{total_items}")
                    tmdb_id = None
                    expired = None
                    if self.config.Cache:
                        tmdb_id, expired = self.config.Cache.query_letterboxd_map(letterboxd_id)
                    if not tmdb_id or expired is not False:
                        try:
                            tmdb_id = self._tmdb(f"{base_url}{slug}", language)
                        except Failed as e:
                            logger.error(e)
                            continue
                        if self.config.Cache:
                            self.config.Cache.update_letterboxd_map(expired, letterboxd_id, tmdb_id)
                    ids.append((tmdb_id, "tmdb"))
                logger.info(f"Processed {total_items} TMDb IDs")
                return ids
            else:
                raise Failed(f"Letterboxd Error: No List Items found in {data}")
        else:
            raise Failed(f"Letterboxd Error: Method {method} not supported")
