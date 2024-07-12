import {createGlobalStore} from "hox";
import {useMemo, useState} from "react";

import {initPlasmicLoader} from "@plasmicapp/loader-react";


function usePlasmic() {
    const [plasmicOpts, setPlasmicOpts] = useState(null)
    const PLASMIC = useMemo(() => {
        return plasmicOpts ? initPlasmicLoader(plasmicOpts) : undefined
    }, [plasmicOpts]);

    return {PLASMIC, setPlasmicOpts};
}

export const [usePlasmicStore] = createGlobalStore(usePlasmic);
