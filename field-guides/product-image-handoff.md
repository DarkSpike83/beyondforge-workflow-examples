# Download product images from a URL list and deliver only the changed files

A distributor sends a studio two catalog exports a week apart. Both contain the same front-photo URL for SKU `BOX-04`. The studio replaced the image at that address. Comparing URL strings would miss the change.

This example uses two tiny ZIPs of original synthetic images. You can inspect both handoffs without an account. The CSV addresses use a reserved example domain for illustration. When running the Actor on your own catalog, use direct, authorized HTTPS image URLs and confirm that you may download and redistribute the images. A CDN variant URL identifies the bytes served for that variant. [Product Image Handoff on Apify](https://apify.com/beyondforge/product-image-handoff)

### First delivery

Open the [first CSV](../examples/product-image-handoff/catalog-1.csv), the [complete ZIP](../examples/product-image-handoff/delivery-1.zip) and its [manifest](../examples/product-image-handoff/manifest-1.json). The CSV supplies the SKU, gallery position and image address. The ZIP contains three images and its own copy of the manifest. Keep the manifest privately with its catalog ID and the delivery date. A stable SKU and position identify each photo across deliveries.

### Second delivery

Open the [second CSV](../examples/product-image-handoff/catalog-2.csv), [changed-files ZIP](../examples/product-image-handoff/delivery-2.zip) and [second manifest](../examples/product-image-handoff/manifest-2.json). For a real professional run, submit the current rows with the same `catalogId`, the entire first manifest in `previousManifest`, and `zipMode` set to `changed`. The complete manifest lists each submitted position. The ZIP includes only the new and changed image files, plus the manifest.

| SKU and position | What happened | Action for the receiving studio |
|---|---|---|
| BOX-04, front (1) | Same address, new bytes. The original PNG was replaced by a JPEG. | Accept `images/BOX-04--1.jpg` after checking its hash. If your catalog still points at `images/BOX-04--1.png`, update that reference and review retirement of the previous file. |
| BOX-04, side (2) | The address and bytes stayed the same. | Keep the existing PNG. Its SHA-256 appears in the manifest, and no duplicate file ships in the second ZIP. |
| TRAY-02, front (1) | A new SKU and photo arrived. | Add the PNG after verifying its SHA-256. |
| TAG-09, front (1) | This position appeared only in the first CSV. | Confirm whether the second input covers the entire catalog. An omitted position can indicate a partial export. The Actor does not instruct your system to delete the old image. |

### Verify the files

Download the [example folder](../examples/product-image-handoff) and run the following command inside it using Python 3.8 or later. The verifier reads local files, checks each embedded manifest, recalculates file sizes and hashes, confirms the contents of each ZIP, and reports omitted positions for review.

```sh
python verify_handoff.py
```

The first ZIP has SHA-256 `77fc632f6d373fc6511438c46472c203e681993fff2d1bad911027b3dd008eb1`. The second has SHA-256 `44c5361a6aad74f2785fc264eca8384e6eeffca0ae3a978b5f41be4799d82223`. Keep the receiving system's previous version until the replacement is verified and accepted. SHA-256 confirms that two sets of bytes match; obtain the expected digest through your trusted delivery channel.

### Try it on your catalog

Start with the [free synthetic repeat handoff](https://apify.com/beyondforge/product-image-handoff/examples/image-version-control-incremental-sku-zip), then use the free preview for up to three images you are authorized to distribute. A professional run on a paying Apify account costs **USD 0.79 per completed package of up to 50 positions**, with explicit charge acceptance. A complete comparison that finds no image changes still delivers the full manifest and costs USD 0.79. In that case the ZIP contains the manifest alone. A new independently started professional run is a new order.

Production use requires your own private storage and account permissions. The downloads here are offline synthetic examples. They contain no customer image, customer run ID, credentials or production billing evidence.

### Free synthetic examples

- [Download images from CSV and name each file by SKU](https://apify.com/beyondforge/product-image-handoff/examples/download-images-from-csv-by-sku)
- [Detect a replacement photo at the same supplier URL](https://apify.com/beyondforge/product-image-handoff/examples/image-change-detection-same-supplier-url)
- [Verify an unchanged catalog with image checksums](https://apify.com/beyondforge/product-image-handoff/examples/image-checksum-unchanged-catalog)
- [Package new and changed SKU images for a repeat handoff](https://apify.com/beyondforge/product-image-handoff/examples/image-version-control-incremental-sku-zip)
- [Export a product image gallery in SKU position order](https://apify.com/beyondforge/product-image-handoff/examples/product-image-gallery-position-export)
- [Match a shared product photo to two variant SKUs](https://apify.com/beyondforge/product-image-handoff/examples/product-image-management-shared-variant-photo)
