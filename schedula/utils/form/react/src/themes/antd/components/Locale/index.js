import {useLocaleStore} from "../../models/locale";

const Locale = ({children, ...props}) => {
    const extraProps = useLocaleStore()
    return children({...props, ...extraProps})
}

export default Locale;