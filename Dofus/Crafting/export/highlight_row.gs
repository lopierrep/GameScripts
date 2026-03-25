/**
 * Resalta la fila activa al hacer click en cualquier celda.
 *
 * Cómo instalar:
 *   1. Abre el Google Sheet
 *   2. Extensiones → Apps Script
 *   3. Pega este código y guarda (Ctrl+S)
 *   4. No hace falta ejecutarlo manualmente — onSelectionChange se activa automáticamente
 */

var HIGHLIGHT_COLOR = "#E8F4FD"; // Azul claro

function onSelectionChange(e) {
  var sheet = e.range.getSheet();
  var numCols = sheet.getLastColumn();
  var currentRow = e.range.getRow();
  var props = PropertiesService.getScriptProperties();
  var key = "lastRow_" + sheet.getSheetId();
  var lastRow = parseInt(props.getProperty(key) || "0");

  // Limpiar solo la fila anterior
  if (lastRow > 1) {
    sheet.getRange(lastRow, 1, 1, numCols).setBackground(null);
  }

  // Resaltar fila actual (ignorar encabezado)
  if (currentRow > 1) {
    sheet.getRange(currentRow, 1, 1, numCols).setBackground(HIGHLIGHT_COLOR);
    props.setProperty(key, currentRow.toString());
  } else {
    props.deleteProperty(key);
  }
}
