import {applyChange, diff} from "deep-diff";
import cloneDeep from "lodash/cloneDeep";
import cjson from "compressed-json";
import hash from "object-hash";

const applyChanges = (target, changes) => {
        changes.forEach((change) => applyChange(target, null, change))
        return target
    },
    buildData = (changes, currentDate) => {
        changes = changes.filter(
            ([date, data], i) => (i === 0 || date <= currentDate)
        )
        return changes.slice(1).reduce(
            (target, [date, data]) => applyChanges(target, data),
            cloneDeep(changes[0][1])
        )
    },
    readChanges = (key) => {
        let storage = (window.sessionStorage.getItem(key) || ''),
            changes = storage.slice(28);
        changes = (changes ? cjson.decompress.fromString(changes) : [])
        return {lastHash: storage.slice(0, 28), changes}
    },
    readDiffList = (key, currentData) => {
        let dataHash = hash(currentData, {
            'algorithm': 'sha1',
            'encoding': 'base64'
        }), {lastHash, changes} = readChanges(key);
        if (lastHash === dataHash) {
            changes = changes.slice(0, changes.length - 1)
        }
        return {
            changes, diffList: changes.map(([date, _, oldHash]) => ({
                date, sameAsCurrent: dataHash === oldHash
            })).reverse()
        }
    },
    cleanStorage=(storeKey)=>{
                    window.sessionStorage.removeItem(storeKey)},
    storeData = (key, formData) => {
        let dataHash = hash(formData, {
                'algorithm': 'sha1',
                'encoding': 'base64'
            }),
            storage = window.sessionStorage.getItem(key) || '';

        if (storage.slice(0, 28) !== dataHash) {
            let data, changes = storage.slice(28);
            changes = changes ? cjson.decompress.fromString(changes) : [];
            let currentDate = Math.floor(Date.now() / 60000);
            changes = changes.filter(
                ([date, data], i) => (date < currentDate)
            )
            if (changes.length) {
                data = diff(changes.slice(1).reduce(
                    (target, [date, data]) => applyChanges(target, data),
                    cloneDeep(changes[0][1])
                ), formData)
                if (!data) {
                    return
                }
            } else {
                data = formData
            }
            changes.push([currentDate, data, dataHash])

            window.sessionStorage.setItem(
                key, `${dataHash}${cjson.compress.toString(changes)}`
            );

        }
    };
export {readDiffList, storeData, buildData, cleanStorage}