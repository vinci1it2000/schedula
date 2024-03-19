import toPathSchema from "./toPathSchema";
import retrieveSchema from "./retrieveSchema";
import isFilesArray from "./isFilesArray";

export default function patchSchemaUtils(schemaUtils) {
    schemaUtils.toPathSchema = (schema, name, formData) => {
        return toPathSchema(schemaUtils.validator, schema, name, schemaUtils.rootSchema, formData);
    }
    schemaUtils.retrieveSchema = (schema, formData) => {
        return retrieveSchema(schemaUtils.validator, schema, schemaUtils.rootSchema, formData);
    }
    schemaUtils.isFilesArray = (schema, formData) => {
        return isFilesArray(schemaUtils.validator, schema, schemaUtils.rootSchema, formData);
    }
    return schemaUtils
}