import get from "lodash/get"
import isEqual from "lodash/isEqual"
import set from "lodash/set"
import times from "lodash/times"
import transform from "lodash/transform"
import merge from "lodash/merge"
import flattenDeep from "lodash/flattenDeep"
import uniq from "lodash/uniq"
import mergeAllOf from "json-schema-merge-allof"

import {
    ADDITIONAL_PROPERTIES_KEY,
    ADDITIONAL_PROPERTY_FLAG,
    ALL_OF_KEY,
    ANY_OF_KEY,
    DEPENDENCIES_KEY,
    IF_KEY,
    ONE_OF_KEY,
    REF_KEY,
    PROPERTIES_KEY,
    ITEMS_KEY,
    findSchemaDefinition,
    getDiscriminatorFieldFromSchema,
    mergeSchemas,
    isObject,
    guessType
} from "@rjsf/utils"
import {getFirstMatchingOption} from './toPathSchema'
import {splitKeyElementFromObject} from "@rjsf/utils/lib/findSchemaDefinition"

/** Retrieves an expanded schema that has had all of its conditions, additional properties, references and dependencies
 * resolved and merged into the `schema` given a `validator`, `rootSchema` and `rawFormData` that is used to do the
 * potentially recursive resolution.
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be forwarded to all the APIs
 * @param schema - The schema for which retrieving a schema is desired
 * @param [rootSchema={}] - The root schema that will be forwarded to all the APIs
 * @param [rawFormData] - The current formData, if any, to assist retrieving a schema
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - The schema having its conditions, additional properties, references and dependencies resolved
 */
export default function retrieveSchema(
    validator,
    schema,
    rootSchema = {},
    rawFormData,
    experimental_customMergeAllOf
) {
    return retrieveSchemaInternal(
        validator,
        schema,
        rootSchema,
        rawFormData,
        undefined,
        undefined,
        experimental_customMergeAllOf
    )[0]
}

/** Resolves a conditional block (if/else/then) by removing the condition and merging the appropriate conditional branch
 * with the rest of the schema. If `expandAllBranches` is true, then the `retrieveSchemaInteral()` results for both
 * conditions will be returned.
 *
 * @param validator - An implementation of the `ValidatorType` interface that is used to detect valid schema conditions
 * @param schema - The schema for which resolving a condition is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param expandAllBranches - Flag, if true, will return all possible branches of conditions, any/oneOf and
 *          dependencies as a list of schemas
 * @param recurseList - The list of recursive references already processed
 * @param [formData] - The current formData to assist retrieving a schema
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - A list of schemas with the appropriate conditions resolved, possibly with all branches expanded
 */
export function resolveCondition(
    validator,
    schema,
    rootSchema,
    expandAllBranches,
    recurseList,
    formData,
    experimental_customMergeAllOf
) {
    const {
        if: expression,
        then,
        else: otherwise,
        ...resolvedSchemaLessConditional
    } = schema

    const conditionValue = validator.isValid(
        expression,
        formData || {},
        rootSchema
    )
    let resolvedSchemas = [resolvedSchemaLessConditional]
    let schemas = []
    if (expandAllBranches) {
        if (then && typeof then !== "boolean") {
            schemas = schemas.concat(
                retrieveSchemaInternal(
                    validator,
                    then,
                    rootSchema,
                    formData,
                    expandAllBranches,
                    recurseList,
                    experimental_customMergeAllOf
                )
            )
        }
        if (otherwise && typeof otherwise !== "boolean") {
            schemas = schemas.concat(
                retrieveSchemaInternal(
                    validator,
                    otherwise,
                    rootSchema,
                    formData,
                    expandAllBranches,
                    recurseList,
                    experimental_customMergeAllOf
                )
            )
        }
    } else {
        const conditionalSchema = conditionValue ? then : otherwise
        if (conditionalSchema && typeof conditionalSchema !== "boolean") {
            schemas = schemas.concat(
                retrieveSchemaInternal(
                    validator,
                    conditionalSchema,
                    rootSchema,
                    formData,
                    expandAllBranches,
                    recurseList,
                    experimental_customMergeAllOf
                )
            )
        }
    }
    if (schemas.length) {
        resolvedSchemas = schemas.map(s =>
            mergeSchemas(resolvedSchemaLessConditional, s)
        )
    }
    return resolvedSchemas.flatMap(s =>
        retrieveSchemaInternal(
            validator,
            s,
            rootSchema,
            formData,
            expandAllBranches,
            recurseList,
            experimental_customMergeAllOf
        )
    )
}

/** Given a list of lists of allOf, anyOf or oneOf values, create a list of lists of all permutations of the values. The
 * `listOfLists` is expected to be all resolved values of the 1st...nth schemas within an `allOf`, `anyOf` or `oneOf`.
 * From those lists, build a matrix for each `xxxOf` where there is more than one schema for a row in the list of lists.
 *
 * For example:
 * - If there are three xxxOf rows (A, B, C) and they have been resolved such that there is only one A, two B and three
 *   C schemas then:
 *   - The permutation for the first row is `[[A]]`
 *   - The permutations for the second row are `[[A,B1], [A,B2]]`
 *   - The permutations for the third row are `[[A,B1,C1], [A,B1,C2], [A,B1,C3], [A,B2,C1], [A,B2,C2], [A,B2,C3]]`
 *
 * @param listOfLists - The list of lists of elements that represent the allOf, anyOf or oneOf resolved values in order
 * @returns - The list of all permutations of schemas for a set of `xxxOf`s
 */
export function getAllPermutationsOfXxxOf(listOfLists) {
    const allPermutations = listOfLists.reduce(
        (permutations, list) => {
            // When there are more than one set of schemas for a row, duplicate the set of permutations and add in the values
            if (list.length > 1) {
                return list.flatMap(element =>
                    times(permutations.length, i => [...permutations[i]].concat(element))
                )
            }
            // Otherwise just push in the single value into the current set of permutations
            permutations.forEach(permutation => permutation.push(list[0]))
            return permutations
        },
        [[]]
    )

    return allPermutations
}

/** Resolves references and dependencies within a schema and its 'allOf' children. Passes the `expandAllBranches` flag
 * down to the `retrieveSchemaInternal()`, `resolveReference()` and `resolveDependencies()` helper calls. If
 * `expandAllBranches` is true, then all possible dependencies and/or allOf branches are returned.
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be forwarded to all the APIs
 * @param schema - The schema for which resolving a schema is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param expandAllBranches - Flag, if true, will return all possible branches of conditions, any/oneOf and dependencies
 *          as a list of schemas
 * @param recurseList - The list of recursive references already processed
 * @param [formData] - The current formData, if any, to assist retrieving a schema
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - The list of schemas having its references, dependencies and allOf schemas resolved
 */
export function resolveSchema(
    validator,
    schema,
    rootSchema,
    expandAllBranches,
    recurseList,
    formData,
    experimental_customMergeAllOf
) {
    const updatedSchemas = resolveReference(
        validator,
        schema,
        rootSchema,
        expandAllBranches,
        recurseList,
        formData
    )
    if (updatedSchemas.length > 1 || updatedSchemas[0] !== schema) {
        // return the updatedSchemas array if it has either multiple schemas within it
        // OR the first schema is not the same as the original schema
        return updatedSchemas
    }
    if (DEPENDENCIES_KEY in schema) {
        const resolvedSchemas = resolveDependencies(
            validator,
            schema,
            rootSchema,
            expandAllBranches,
            recurseList,
            formData
        )
        return resolvedSchemas.flatMap(s => {
            return retrieveSchemaInternal(
                validator,
                s,
                rootSchema,
                formData,
                expandAllBranches,
                recurseList,
                experimental_customMergeAllOf
            )
        })
    }
    if (ALL_OF_KEY in schema && Array.isArray(schema.allOf)) {
        const allOfSchemaElements = schema.allOf.map(allOfSubschema =>
            retrieveSchemaInternal(
                validator,
                allOfSubschema,
                rootSchema,
                formData,
                expandAllBranches,
                recurseList,
                experimental_customMergeAllOf
            )
        )
        const allPermutations = getAllPermutationsOfXxxOf(allOfSchemaElements)
        return allPermutations.map(permutation => ({
            ...schema,
            allOf: permutation
        }))
    }
    // No $ref or dependencies or allOf attribute was found, returning the original schema.
    return [schema]
}

/** Resolves all references within a schema and then returns the `retrieveSchemaInternal()` if the resolved schema is
 * actually different than the original. Passes the `expandAllBranches` flag down to the `retrieveSchemaInternal()`
 * helper call.
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be forwarded to all the APIs
 * @param schema - The schema for which resolving a reference is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param expandAllBranches - Flag, if true, will return all possible branches of conditions, any/oneOf and dependencies
 *          as a list of schemas
 * @param recurseList - The list of recursive references already processed
 * @param [formData] - The current formData, if any, to assist retrieving a schema
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - The list schemas retrieved after having all references resolved
 */
export function resolveReference(
    validator,
    schema,
    rootSchema,
    expandAllBranches,
    recurseList,
    formData,
    experimental_customMergeAllOf
) {
    const updatedSchema = resolveAllReferences(schema, rootSchema, recurseList)
    if (updatedSchema !== schema) {
        // Only call this if the schema was actually changed by the `resolveAllReferences()` function
        return retrieveSchemaInternal(
            validator,
            updatedSchema,
            rootSchema,
            formData,
            expandAllBranches,
            recurseList,
            experimental_customMergeAllOf
        )
    }
    return [schema]
}

/** Resolves all references within the schema itself as well as any of its properties and array items.
 *
 * @param schema - The schema for which resolving all references is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param recurseList - List of $refs already resolved to prevent recursion
 * @returns - given schema will all references resolved or the original schema if no internal `$refs` were resolved
 */
export function resolveAllReferences(schema, rootSchema, recurseList) {
    if (!isObject(schema)) {
        return schema
    }
    let resolvedSchema = schema
    // resolve top level ref
    if (REF_KEY in resolvedSchema) {
        const {$ref, ...localSchema} = resolvedSchema
        // Check for a recursive reference and stop the loop
        if (recurseList.includes($ref)) {
            return resolvedSchema
        }
        recurseList.push($ref)
        // Retrieve the referenced schema definition.
        const refSchema = findSchemaDefinition($ref, rootSchema)
        resolvedSchema = {...refSchema, ...localSchema}
    }

    if (PROPERTIES_KEY in resolvedSchema) {
        const childrenLists = []
        const updatedProps = transform(
            resolvedSchema[PROPERTIES_KEY],
            (result, value, key) => {
                const childList = [...recurseList]
                result[key] = resolveAllReferences(value, rootSchema, childList)
                childrenLists.push(childList)
            },
            {}
        )
        merge(recurseList, uniq(flattenDeep(childrenLists)))
        resolvedSchema = {...resolvedSchema, [PROPERTIES_KEY]: updatedProps}
    }

    if (
        ITEMS_KEY in resolvedSchema &&
        !Array.isArray(resolvedSchema.items) &&
        typeof resolvedSchema.items !== "boolean"
    ) {
        resolvedSchema = {
            ...resolvedSchema,
            items: resolveAllReferences(resolvedSchema.items, rootSchema, recurseList)
        }
    }

    return isEqual(schema, resolvedSchema) ? schema : resolvedSchema
}

/** Creates new 'properties' items for each key in the `formData`
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be used when necessary
 * @param theSchema - The schema for which the existing additional properties is desired
 * @param [rootSchema] - The root schema, used to primarily to look up `$ref`s * @param validator
 * @param [aFormData] - The current formData, if any, to assist retrieving a schema
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - The updated schema with additional properties stubbed
 */
export function stubExistingAdditionalProperties(
    validator,
    theSchema,
    rootSchema,
    aFormData,
    experimental_customMergeAllOf
) {
    // Clone the schema so that we don't ruin the consumer's original
    const schema = {
        ...theSchema,
        properties: {...theSchema.properties}
    }

    // make sure formData is an object
    const formData = aFormData && isObject(aFormData) ? aFormData : {}
    Object.keys(formData).forEach(key => {
        if (key in schema.properties) {
            // No need to stub, our schema already has the property
            return
        }

        let additionalProperties = {}
        if (typeof schema.additionalProperties !== "boolean") {
            if (REF_KEY in schema.additionalProperties) {
                additionalProperties = retrieveSchema(
                    validator,
                    {
                        $ref: get(schema.additionalProperties, [REF_KEY])
                    },
                    rootSchema,
                    formData,
                    experimental_customMergeAllOf
                )
            } else if ("type" in schema.additionalProperties) {
                additionalProperties = {...schema.additionalProperties}
            } else if (
                ANY_OF_KEY in schema.additionalProperties ||
                ONE_OF_KEY in schema.additionalProperties
            ) {
                additionalProperties = {
                    type: "object",
                    ...schema.additionalProperties
                }
            } else {
                additionalProperties = {type: guessType(get(formData, [key]))}
            }
        } else {
            additionalProperties = {type: guessType(get(formData, [key]))}
        }

        // The type of our new key should match the additionalProperties value;
        schema.properties[key] = additionalProperties
        // Set our additional property flag so we know it was dynamically added
        set(schema.properties, [key, ADDITIONAL_PROPERTY_FLAG], true)
    })

    return schema
}

/** Internal handler that retrieves an expanded schema that has had all of its conditions, additional properties,
 * references and dependencies resolved and merged into the `schema` given a `validator`, `rootSchema` and `rawFormData`
 * that is used to do the potentially recursive resolution. If `expandAllBranches` is true, then all possible branches
 * of the schema and its references, conditions and dependencies are returned.
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be forwarded to all the APIs
 * @param schema - The schema for which retrieving a schema is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param [rawFormData] - The current formData, if any, to assist retrieving a schema
 * @param [expandAllBranches=false] - Flag, if true, will return all possible branches of conditions, any/oneOf and
 *          dependencies as a list of schemas
 * @param [recurseList=[]] - The optional, list of recursive references already processed
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - The schema(s) resulting from having its conditions, additional properties, references and dependencies
 *          resolved. Multiple schemas may be returned if `expandAllBranches` is true.
 */
export function retrieveSchemaInternal(
    validator,
    schema,
    rootSchema,
    rawFormData,
    expandAllBranches = false,
    recurseList = [],
    experimental_customMergeAllOf
) {
    if (!isObject(schema)) {
        return [{}]
    }
    const resolvedSchemas = resolveSchema(
        validator,
        schema,
        rootSchema,
        expandAllBranches,
        recurseList,
        rawFormData,
        experimental_customMergeAllOf
    )
    return resolvedSchemas.flatMap(s => {
        let resolvedSchema = s
        if (IF_KEY in resolvedSchema) {
            return resolveCondition(
                validator,
                resolvedSchema,
                rootSchema,
                expandAllBranches,
                recurseList,
                rawFormData,
                experimental_customMergeAllOf
            )
        }
        if (ALL_OF_KEY in resolvedSchema) {
            // resolve allOf schemas
            if (expandAllBranches) {
                const {allOf, ...restOfSchema} = resolvedSchema
                return [...allOf, restOfSchema]
            }
            try {
                const withContainsSchemas = []
                const withoutContainsSchemas = []
                resolvedSchema.allOf?.forEach(s => {
                    if (typeof s === "object" && s.contains) {
                        withContainsSchemas.push(s)
                    } else {
                        withoutContainsSchemas.push(s)
                    }
                })
                if (withContainsSchemas.length) {
                    resolvedSchema = {
                        ...resolvedSchema,
                        allOf: withoutContainsSchemas
                    }
                }
                resolvedSchema = experimental_customMergeAllOf
                    ? experimental_customMergeAllOf(resolvedSchema)
                    : mergeAllOf(resolvedSchema, {
                        deep: false
                    })
                if (withContainsSchemas.length) {
                    resolvedSchema.allOf = withContainsSchemas
                }
            } catch (e) {
                console.warn("could not merge subschemas in allOf:\n", e)
                const {allOf, ...resolvedSchemaWithoutAllOf} = resolvedSchema
                return resolvedSchemaWithoutAllOf
            }
        }
        const hasAdditionalProperties =
            ADDITIONAL_PROPERTIES_KEY in resolvedSchema &&
            resolvedSchema.additionalProperties !== false
        if (hasAdditionalProperties) {
            return stubExistingAdditionalProperties(
                validator,
                resolvedSchema,
                rootSchema,
                rawFormData,
                experimental_customMergeAllOf
            )
        }

        return resolvedSchema
    })
}

/** Resolves an `anyOf` or `oneOf` within a schema (if present) to the list of schemas returned from
 * `retrieveSchemaInternal()` for the best matching option. If `expandAllBranches` is true, then a list of schemas for ALL
 * options are retrieved and returned.
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be forwarded to all the APIs
 * @param schema - The schema for which retrieving a schema is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param expandAllBranches - Flag, if true, will return all possible branches of conditions, any/oneOf and dependencies
 *          as a list of schemas
 * @param [rawFormData] - The current formData, if any, to assist retrieving a schema, defaults to an empty object
 * @returns - Either an array containing the best matching option or all options if `expandAllBranches` is true
 */
export function resolveAnyOrOneOfSchemas(
    validator,
    schema,
    rootSchema,
    expandAllBranches,
    rawFormData
) {
    let anyOrOneOf
    const {oneOf, anyOf, ...remaining} = schema
    if (Array.isArray(oneOf)) {
        anyOrOneOf = oneOf
    } else if (Array.isArray(anyOf)) {
        anyOrOneOf = anyOf
    }
    if (anyOrOneOf) {
        // Ensure that during expand all branches we pass an object rather than undefined so that all options are interrogated
        const formData =
            rawFormData === undefined && expandAllBranches ? {} : rawFormData
        const discriminator = getDiscriminatorFieldFromSchema(schema)
        anyOrOneOf = anyOrOneOf.map(s => {
            // Due to anyOf/oneOf possibly using the same $ref we always pass a fresh recurse list array so that each option
            // can resolve recursive references independently
            return resolveAllReferences(s, rootSchema, [])
        })
        // Call this to trigger the set of isValid() calls that the schema parser will need
        const option = getFirstMatchingOption(
            validator,
            formData,
            anyOrOneOf,
            rootSchema,
            discriminator
        )
        if (expandAllBranches) {
            return anyOrOneOf.map(item => mergeSchemas(remaining, item))
        }
        schema = mergeSchemas(remaining, anyOrOneOf[option])
    }
    return [schema]
}

/** Resolves dependencies within a schema and its 'anyOf/oneOf' children. Passes the `expandAllBranches` flag down to
 * the `resolveAnyOrOneOfSchema()` and `processDependencies()` helper calls.
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be forwarded to all the APIs
 * @param schema - The schema for which resolving a dependency is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param expandAllBranches - Flag, if true, will return all possible branches of conditions, any/oneOf and dependencies
 *          as a list of schemas
 * @param recurseList - The list of recursive references already processed
 * @param [formData] - The current formData, if any, to assist retrieving a schema
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - The list of schemas with their dependencies resolved
 */
export function resolveDependencies(
    validator,
    schema,
    rootSchema,
    expandAllBranches,
    recurseList,
    formData,
    experimental_customMergeAllOf
) {
    // Drop the dependencies from the source schema.
    const {dependencies, ...remainingSchema} = schema
    const resolvedSchemas = resolveAnyOrOneOfSchemas(
        validator,
        remainingSchema,
        rootSchema,
        expandAllBranches,
        formData
    )
    return resolvedSchemas.flatMap(resolvedSchema =>
        processDependencies(
            validator,
            dependencies,
            resolvedSchema,
            rootSchema,
            expandAllBranches,
            recurseList,
            formData,
            experimental_customMergeAllOf
        )
    )
}

/** Processes all the `dependencies` recursively into the list of `resolvedSchema`s as needed. Passes the
 * `expandAllBranches` flag down to the `withDependentSchema()` and the recursive `processDependencies()` helper calls.
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be forwarded to all the APIs
 * @param dependencies - The set of dependencies that needs to be processed
 * @param resolvedSchema - The schema for which processing dependencies is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param expandAllBranches - Flag, if true, will return all possible branches of conditions, any/oneOf and dependencies
 *          as a list of schemas
 * @param recurseList - The list of recursive references already processed
 * @param [formData] - The current formData, if any, to assist retrieving a schema
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - The schema with the `dependencies` resolved into it
 */
export function processDependencies(
    validator,
    dependencies,
    resolvedSchema,
    rootSchema,
    expandAllBranches,
    recurseList,
    formData,
    experimental_customMergeAllOf
) {
    let schemas = [resolvedSchema]
    // Process dependencies updating the local schema properties as appropriate.
    for (const dependencyKey in dependencies) {
        // Skip this dependency if its trigger property is not present.
        if (!expandAllBranches && get(formData, [dependencyKey]) === undefined) {
            continue
        }
        // Skip this dependency if it is not included in the schema (such as when dependencyKey is itself a hidden dependency.)
        if (
            resolvedSchema.properties &&
            !(dependencyKey in resolvedSchema.properties)
        ) {
            continue
        }
        const [remainingDependencies, dependencyValue] = splitKeyElementFromObject(
            dependencyKey,
            dependencies
        )
        if (Array.isArray(dependencyValue)) {
            schemas[0] = withDependentProperties(resolvedSchema, dependencyValue)
        } else if (isObject(dependencyValue)) {
            schemas = withDependentSchema(
                validator,
                resolvedSchema,
                rootSchema,
                dependencyKey,
                dependencyValue,
                expandAllBranches,
                recurseList,
                formData,
                experimental_customMergeAllOf
            )
        }
        return schemas.flatMap(schema =>
            processDependencies(
                validator,
                remainingDependencies,
                schema,
                rootSchema,
                expandAllBranches,
                recurseList,
                formData,
                experimental_customMergeAllOf
            )
        )
    }
    return schemas
}

/** Updates a schema with additionally required properties added
 *
 * @param schema - The schema for which resolving a dependent properties is desired
 * @param [additionallyRequired] - An optional array of additionally required names
 * @returns - The schema with the additional required values merged in
 */
export function withDependentProperties(schema, additionallyRequired) {
    if (!additionallyRequired) {
        return schema
    }
    const required = Array.isArray(schema.required)
        ? Array.from(new Set([...schema.required, ...additionallyRequired]))
        : additionallyRequired
    return {...schema, required: required}
}

/** Merges a dependent schema into the `schema` dealing with oneOfs and references. Passes the `expandAllBranches` flag
 * down to the `retrieveSchemaInternal()`, `resolveReference()` and `withExactlyOneSubschema()` helper calls.
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be forwarded to all the APIs
 * @param schema - The schema for which resolving a dependent schema is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param dependencyKey - The key name of the dependency
 * @param dependencyValue - The potentially dependent schema
 * @param expandAllBranches - Flag, if true, will return all possible branches of conditions, any/oneOf and dependencies
 *          as a list of schemas
 * @param recurseList - The list of recursive references already processed
 * @param [formData]- The current formData to assist retrieving a schema
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - The list of schemas with the dependent schema resolved into them
 */
export function withDependentSchema(
    validator,
    schema,
    rootSchema,
    dependencyKey,
    dependencyValue,
    expandAllBranches,
    recurseList,
    formData,
    experimental_customMergeAllOf
) {
    const dependentSchemas = retrieveSchemaInternal(
        validator,
        dependencyValue,
        rootSchema,
        formData,
        expandAllBranches,
        recurseList,
        experimental_customMergeAllOf
    )
    return dependentSchemas.flatMap(dependent => {
        const {oneOf, ...dependentSchema} = dependent
        schema = mergeSchemas(schema, dependentSchema)
        // Since it does not contain oneOf, we return the original schema.
        if (oneOf === undefined) {
            return schema
        }
        // Resolve $refs inside oneOf.
        const resolvedOneOfs = oneOf.map(subschema => {
            if (typeof subschema === "boolean" || !(REF_KEY in subschema)) {
                return [subschema]
            }
            return resolveReference(
                validator,
                subschema,
                rootSchema,
                expandAllBranches,
                recurseList,
                formData
            )
        })
        const allPermutations = getAllPermutationsOfXxxOf(resolvedOneOfs)
        return allPermutations.flatMap(resolvedOneOf =>
            withExactlyOneSubschema(
                validator,
                schema,
                rootSchema,
                dependencyKey,
                resolvedOneOf,
                expandAllBranches,
                recurseList,
                formData,
                experimental_customMergeAllOf
            )
        )
    })
}

/** Returns a list of `schema`s with the best choice from the `oneOf` options merged into it. If `expandAllBranches` is
 * true, then a list of schemas for ALL options are retrieved and returned. Passes the `expandAllBranches` flag down to
 * the `retrieveSchemaInternal()` helper call.
 *
 * @param validator - An implementation of the `ValidatorType` interface that will be used to validate oneOf options
 * @param schema - The schema for which resolving a oneOf subschema is desired
 * @param rootSchema - The root schema that will be forwarded to all the APIs
 * @param dependencyKey - The key name of the oneOf dependency
 * @param oneOf - The list of schemas representing the oneOf options
 * @param expandAllBranches - Flag, if true, will return all possible branches of conditions, any/oneOf and dependencies
 *          as a list of schemas
 * @param recurseList - The list of recursive references already processed
 * @param [formData] - The current formData to assist retrieving a schema
 * @param [experimental_customMergeAllOf] - Optional function that allows for custom merging of `allOf` schemas
 * @returns - Either an array containing the best matching option or all options if `expandAllBranches` is true
 */
export function withExactlyOneSubschema(
    validator,
    schema,
    rootSchema,
    dependencyKey,
    oneOf,
    expandAllBranches,
    recurseList,
    formData,
    experimental_customMergeAllOf
) {
    const validSubschemas = oneOf.filter(subschema => {
        if (typeof subschema === "boolean" || !subschema || !subschema.properties) {
            return false
        }
        const {[dependencyKey]: conditionPropertySchema} = subschema.properties
        if (conditionPropertySchema) {
            const conditionSchema = {
                type: "object",

                properties: {
                    [dependencyKey]: conditionPropertySchema
                }
            }
            return (
                validator.isValid(conditionSchema, formData, rootSchema) ||
                expandAllBranches
            )
        }
        return false
    })

    if (!expandAllBranches && validSubschemas.length !== 1) {
        console.warn(
            "ignoring oneOf in dependencies because there isn't exactly one subschema that is valid"
        )
        return [schema]
    }
    return validSubschemas.flatMap(s => {
        const subschema = s
        const [dependentSubschema] = splitKeyElementFromObject(
            dependencyKey,
            subschema.properties
        )
        const dependentSchema = {...subschema, properties: dependentSubschema}
        const schemas = retrieveSchemaInternal(
            validator,
            dependentSchema,
            rootSchema,
            formData,
            expandAllBranches,
            recurseList,
            experimental_customMergeAllOf
        )
        return schemas.map(s => mergeSchemas(schema, s))
    })
}
