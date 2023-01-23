import {createGlobalStore} from "hox";
import {useState} from "react";

function useQuery() {
    const [query, setQuery] = useState({});
    return {query, setQuery};
}

export const [useQueryStore] = createGlobalStore(useQuery);
