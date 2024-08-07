import {UI_WIDGET_KEY} from "@rjsf/utils"
import retrieveSchema from "./retrieveSchema"
import get from 'lodash/get'

/** Checks to see if the `schema` and `uiSchema` combination represents an array of files
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be used when necessary
 * @param schema - The schema for which check for array of files flag is desired
 * @param [uiSchema={}] - The UI schema from which to check the widget
 * @param [rootSchema] - The root schema, used to primarily to look up `$ref`s
 * @returns - True if schema/uiSchema contains an array of files, otherwise false
 */
export default function isFilesArray(
    validator,
    schema,
    uiSchema = {},
    rootSchema
) {
    if (uiSchema[UI_WIDGET_KEY] === "files") {
        return true
    }
    const {items} = schema
    if (items) {
        if ((get(items, 'type', "string") !== "string") ||
            (get(items, 'format', "data-url") !== "data-url")) {
            return false
        }
        const itemsSchema = retrieveSchema(validator, items, rootSchema)
        return itemsSchema.type === "string" && itemsSchema.format === "data-url"
    }
    return false
}
