import {usePlasmicStore} from "../../../models/plasmic";

const PlasmicRegisterContexts = ({children, render, tokens, ...props}) => {
    const {registerTokens} = usePlasmicStore()
    registerTokens(render, tokens)
    return children
}
export default PlasmicRegisterContexts;