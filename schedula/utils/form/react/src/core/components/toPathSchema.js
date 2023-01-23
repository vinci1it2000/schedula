import get from 'lodash/get';
import set from 'lodash/set';
import find from 'lodash/find';
import {
    ALL_OF_KEY,
    ANY_OF_KEY,
    ADDITIONAL_PROPERTIES_KEY,
    DEPENDENCIES_KEY,
    ITEMS_KEY,
    NAME_KEY,
    ONE_OF_KEY,
    PROPERTIES_KEY,
    REF_KEY,
    RJSF_ADDITONAL_PROPERTIES_FLAG,
    retrieveSchema
} from "@rjsf/utils"

export function getFirstMatchingOption(validator, formData, options, rootSchema, name) {
    // For performance, skip validating subschemas if formData is undefined. We just
    // want to get the first option in that case.
    if (formData === undefined) {
        return 0;
    }
    for (let i = 0; i < options.length; i++) {
        const option = options[i];

        // If the schema describes an object then we need to add slightly more
        // strict matching to the schema, because unless the schema uses the
        // "requires" keyword, an object will match the schema as long as it
        // doesn't have matching keys with a conflicting type. To do this we use an
        // "anyOf" with an array of requires. This augmentation expresses that the
        // schema should match if any of the keys in the schema are present on the
        // object and pass validation.
        if (option.properties) {
            if (Object.keys(option.properties).some((key) => (
                key in formData
            )) && Object.entries(option.properties).reduce((res, [key, value]) => (
                res && value.hasOwnProperty('const') ? key in formData && value.const === formData[key] : true
            ), true)) {
                let augmentedSchema = {...option};

                // Remove the "required" field as it's likely that not all fields have
                // been filled in yet, which will mean that the schema is not valid
                delete augmentedSchema.required;

                if (validator.isValid(augmentedSchema, formData, rootSchema)) {
                    return i;
                }
            }
        } else if (option.hasOwnProperty('const')) {
            if (option.const === formData) {
                return i
            }
        } else if (validator.isValid(option, formData, rootSchema)) {
            return i;
        }
    }
    return 0;
}

/** Generates an `PathSchema` object for the `schema`, recursively
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be used when necessary
 * @param schema - The schema for which the `PathSchema` is desired
 * @param [name=''] - The base name for the schema
 * @param [rootSchema] - The root schema, used to primarily to look up `$ref`s
 * @param [formData] - The current formData, if any, to assist retrieving a schema
 * @returns - The `PathSchema` object for the `schema`
 */
export default function toPathSchema(validator, schema, name = '', rootSchema, formData) {
    if (REF_KEY in schema || DEPENDENCIES_KEY in schema || ALL_OF_KEY in schema) {
        const _schema = retrieveSchema(validator, schema, rootSchema, formData);
        return toPathSchema(validator, _schema, name, rootSchema, formData);
    }

    const pathSchema = {
        [NAME_KEY]: name.replace(/^\./, ''),
    };
    if (schema.cascader) {
        const _schema = formData !== undefined ? schema.cascader.reduce((s, k) => {
            let v = {properties: {}}
            v.properties[k] = {const: formData[k]}
            return find(s.oneOf, v)
        }, schema) : {properties: schema.properties};
        return toPathSchema(validator, _schema, name, rootSchema, formData);
    } else if (ONE_OF_KEY in schema) {
        const index = getFirstMatchingOption(validator, formData, schema.oneOf, rootSchema, name);
        const _schema = schema.oneOf[index];
        return toPathSchema(validator, _schema, name, rootSchema, formData);
    }
    if (ANY_OF_KEY in schema) {
        const index = getFirstMatchingOption(validator, formData, schema.anyOf, rootSchema, name);
        const _schema = schema.anyOf[index];
        return toPathSchema(validator, _schema, name, rootSchema, formData);
    }
    if (ADDITIONAL_PROPERTIES_KEY in schema && schema[ADDITIONAL_PROPERTIES_KEY] !== false) {
        set(pathSchema, RJSF_ADDITONAL_PROPERTIES_FLAG, true);
    }

    if (ITEMS_KEY in schema && Array.isArray(formData)) {
        formData.forEach((element, i) => {
            pathSchema[i] = toPathSchema(validator, schema.items, `${name}.${i}`, rootSchema, element);
        });
    } else if (PROPERTIES_KEY in schema) {
        for (const property in schema.properties) {
            const field = get(schema, [PROPERTIES_KEY, property]);
            pathSchema[property] = toPathSchema(validator, field, `${name}.${property}`, rootSchema,
                // It's possible that formData is not an object -- this can happen if an
                // array item has just been added, but not populated with data yet
                get(formData, [property]));
        }
    }

    return pathSchema;
}