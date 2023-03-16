#!/usr/bin/env python

import os
import os.path
import sys
import urllib.parse
import re
from bs4 import BeautifulSoup
import requests
from pathvalidate import sanitize_filepath
from multiprocessing.pool import ThreadPool as Pool
from urllib.parse import urlparse, parse_qs, urljoin


artist = sys.argv[1]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/108.0.0.0 Safari/537.36",
}


def worker(artwork):
    url = artwork["node"]["image"]["url"]
    url = url[:url.rfind('/')] + "/normalized.jpg"

    path = sanitize_filepath(os.path.join("artsy", artist, artwork["node"]["slug"] + os.path.splitext(url)[1]))
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.exists(path):
        print("*** SKIPPING (exists): " + path)
    else:
        resp = requests.get(url)
        if resp.status_code != 200:
            print(f"!!! FAILED saving: {url}")
            return
        print("Saving: " + url)
        with open(path, "wb") as f:
            for chunk in resp:
                f.write(chunk)

    artist_name = artwork["node"]["artistNames"]
    artwork_name = artwork["node"]["title"]
    creationDate = artwork["node"]["date"]
    medium = artwork["node"].get("mediumType", {})
    txt = f"{artist_name}, {artwork_name}, {creationDate}"
    if medium and medium["filterGene"]:
        txt += ", " + medium["filterGene"]["name"]

    txt_name = os.path.splitext(os.path.basename(path))[0] + ".txt"
    txt_path = os.path.join(os.path.dirname(path), txt_name)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(txt)


no = 1
while True:
    print(f"=== Page {no} ===")
    data = {
        "id": "ArtistArtworkFilterQuery",
        "query": "query ArtistArtworkFilterQuery(\n  $artistID: String!\n  $input: FilterArtworksInput\n) {\n  artist(id: $artistID) {\n    ...ArtistArtworkFilter_artist_2VV6jB\n    id\n  }\n}\n\nfragment ArtistArtworkFilter_artist_2VV6jB on Artist {\n  name\n  counts {\n    partner_shows: partnerShows\n    for_sale_artworks: forSaleArtworks\n    ecommerce_artworks: ecommerceArtworks\n    auction_artworks: auctionArtworks\n    artworks\n    has_make_offer_artworks: hasMakeOfferArtworks\n  }\n  filtered_artworks: filterArtworksConnection(first: 30, input: $input) {\n    id\n    counts {\n      total(format: \"0,0\")\n    }\n    ...ArtworkFilterArtworkGrid_filtered_artworks\n  }\n  internalID\n  slug\n}\n\nfragment ArtworkFilterArtworkGrid_filtered_artworks on FilterArtworksConnection {\n  id\n  pageInfo {\n    hasNextPage\n    endCursor\n  }\n  pageCursors {\n    ...Pagination_pageCursors\n  }\n  edges {\n    node {\n      id\n    }\n  }\n  ...ArtworkGrid_artworks\n}\n\nfragment ArtworkGrid_artworks on ArtworkConnectionInterface {\n  __isArtworkConnectionInterface: __typename\n  edges {\n    __typename\n    node {\n      id\n      slug\n      href\n      internalID\n      image(includeAll: false) {\n        aspectRatio\n      }\n      ...GridItem_artwork\n      ...FlatGridItem_artwork\n    }\n    ... on Node {\n      __isNode: __typename\n      id\n    }\n  }\n}\n\nfragment Badge_artwork on Artwork {\n  is_biddable: isBiddable\n  href\n  sale {\n    is_preview: isPreview\n    display_timely_at: displayTimelyAt\n    id\n  }\n}\n\nfragment DeprecatedSaveButton_artwork on Artwork {\n  id\n  internalID\n  slug\n  is_saved: isSaved\n  title\n}\n\nfragment Details_artwork on Artwork {\n  internalID\n  href\n  title\n  date\n  sale_message: saleMessage\n  cultural_maker: culturalMaker\n  artist {\n    targetSupply {\n      isP1\n    }\n    id\n  }\n  marketPriceInsights {\n    demandRank\n  }\n  artists(shallow: true) {\n    id\n    href\n    name\n  }\n  collecting_institution: collectingInstitution\n  partner(shallow: true) {\n    name\n    href\n    id\n  }\n  sale {\n    endAt\n    cascadingEndTimeIntervalMinutes\n    extendedBiddingIntervalMinutes\n    startAt\n    is_auction: isAuction\n    is_closed: isClosed\n    id\n  }\n  sale_artwork: saleArtwork {\n    lotID\n    lotLabel\n    endAt\n    extendedBiddingEndAt\n    formattedEndDateTime\n    counts {\n      bidder_positions: bidderPositions\n    }\n    highest_bid: highestBid {\n      display\n    }\n    opening_bid: openingBid {\n      display\n    }\n    id\n  }\n  ...SaveButton_artwork\n  ...SaveArtworkToListsButton_artwork\n  ...HoverDetails_artwork\n}\n\nfragment FlatGridItem_artwork on Artwork {\n  ...Metadata_artwork\n  ...DeprecatedSaveButton_artwork\n  sale {\n    extendedBiddingPeriodMinutes\n    extendedBiddingIntervalMinutes\n    startAt\n    id\n  }\n  saleArtwork {\n    endAt\n    extendedBiddingEndAt\n    lotID\n    id\n  }\n  internalID\n  title\n  image_title: imageTitle\n  image(includeAll: false) {\n    resized(width: 445, version: [\"larger\", \"large\"]) {\n      src\n      srcSet\n      width\n      height\n    }\n  }\n  artistNames\n  href\n  is_saved: isSaved\n}\n\nfragment GridItem_artwork on Artwork {\n  internalID\n  title\n  imageTitle\n  image(includeAll: false) {\n    internalID\n    placeholder\n    url(version: [\"larger\", \"large\"])\n    aspectRatio\n    versions\n  }\n  artistNames\n  href\n  ...Metadata_artwork\n  ...Badge_artwork\n}\n\nfragment HoverDetails_artwork on Artwork {\n  internalID\n  attributionClass {\n    name\n    id\n  }\n  mediumType {\n    filterGene {\n      name\n      id\n    }\n  }\n}\n\nfragment Metadata_artwork on Artwork {\n  ...Details_artwork\n  internalID\n  href\n}\n\nfragment Pagination_pageCursors on PageCursors {\n  around {\n    cursor\n    page\n    isCurrent\n  }\n  first {\n    cursor\n    page\n    isCurrent\n  }\n  last {\n    cursor\n    page\n    isCurrent\n  }\n  previous {\n    cursor\n    page\n  }\n}\n\nfragment SaveArtworkToListsButton_artwork on Artwork {\n  id\n  internalID\n  is_saved: isSaved\n  slug\n  title\n  date\n  preview: image {\n    url(version: \"square\")\n  }\n  customCollections: collectionsConnection(first: 0, default: false, saves: true) {\n    totalCount\n  }\n}\n\nfragment SaveButton_artwork on Artwork {\n  id\n  internalID\n  slug\n  is_saved: isSaved\n  title\n}\n",
        "variables": {
            "artistID": artist,
            "input": {
                "first": 30,
                "majorPeriods": [],
                "page": no,
                "sizes": [],
                "sort": "-decayed_merch",
                "artistIDs": [],
                "attributionClass": [],
                "partnerIDs": [],
                "additionalGeneIDs": [],
                "colors": [],
                "locationCities": [],
                "artistNationalities": [],
                "materialsTerms": [],
                "height": "*-*",
                "width": "*-*",
                "priceRange": "*-*"
            }
        }
    }
    resp = requests.post(f"https://metaphysics-production.artsy.net/v2", headers=HEADERS, json=data)
    resp = resp.json()
    if "data" not in resp or not resp["data"]["artist"]["filtered_artworks"]["edges"]:
        print("Finished.")
        exit(0)

    p = Pool(processes=8)
    for res in p.imap_unordered(worker, resp["data"]["artist"]["filtered_artworks"]["edges"]):
        pass
    p.close()
    p.join()

    no += 1
