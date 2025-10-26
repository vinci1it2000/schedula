import {usePlasmicStore} from "../../../models/plasmic";

const PlasmicRegisterContexts = ({children, render, contexts, ...props}) => {
    const {registerContexts} = usePlasmicStore()
    registerContexts(render, contexts)
    return children
}
export default PlasmicRegisterContexts;