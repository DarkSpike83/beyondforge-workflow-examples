function prepareExport(bundle, expectedSupplier) {
  const reject = reason => { throw new Error(reason); };
  if (typeof expectedSupplier !== 'string' || !expectedSupplier.trim()) reject('Missing retailer supplier binding');
  function snapshot(doc) {
    if (!doc || doc.supplier !== expectedSupplier || doc.complete !== true ||
        !Number.isSafeInteger(doc.sequence) || doc.sequence < 1 || !Array.isArray(doc.rows) ||
        !Number.isSafeInteger(doc.rowCount) || doc.rowCount < 1 || doc.rowCount > 5000 ||
        doc.rows.length !== doc.rowCount || doc.nextPage != null) reject('Incomplete or unbound supplier export');
    const seen = new Set();
    return {rows: doc.rows.map(row => {
      if (!row || typeof row.sku !== 'string' || row.sku.trim() !== row.sku || !row.sku ||
          seen.has(row.sku) || !Number.isSafeInteger(row.stock) || row.stock < 0 ||
          typeof row.price !== 'string' || !/^\d+(\.\d{1,4})?$/.test(row.price) ||
          typeof row.currency !== 'string' || !/^[A-Z]{3}$/.test(row.currency) ||
          (row.unit !== undefined && (typeof row.unit !== 'string' || !row.unit.trim())) ||
          (row.packSize !== undefined && (!Number.isSafeInteger(row.packSize) || row.packSize < 1)))
        reject('Invalid or duplicate catalog row');
      seen.add(row.sku);
      return Object.fromEntries(['sku','price','stock','currency','unit','packSize']
        .filter(k => row[k] !== undefined).map(k => [k,row[k]]));
    })};
  }
  if (!bundle || typeof bundle !== 'object' || !bundle.current) reject('Missing supplier export');
  const input = {incoming:snapshot(bundle.current)};
  if (bundle.previous !== undefined) {
    input.baseline = snapshot(bundle.previous);
    if (bundle.previous.sequence !== bundle.current.sequence - 1) reject('Baseline sequence mismatch');
  }
  // Three UTF-8 bytes per UTF-16 code unit bounds the encoded size even for surrogate pairs.
  if (JSON.stringify(input).length * 3 + 512 > 4 * 1024 * 1024) reject('Input exceeds conservative transport budget');
  // A supplied pair initializes an empty stream. Later exports must follow the last confirmed revision.
  const previousSequence = input.baseline ? 0 : bundle.current.sequence - 1;
  return {sequence:bundle.current.sequence, previousSequence, expectedIncomingRows:input.incoming.rows.length,input};
}

module.exports = {prepareExport};
