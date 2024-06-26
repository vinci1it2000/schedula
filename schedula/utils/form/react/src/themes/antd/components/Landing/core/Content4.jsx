import React from 'react';
import TweenOne from 'rc-tween-one';
import OverPack from 'rc-scroll-anim/lib/ScrollOverPack';
import VideoPlay from 'react-sublime-video';
import {getChildrenToRender} from './utils';

function Content4(props) {
    const {...tagProps} = props;
    const {dataSource, isMobile} = tagProps;
    delete tagProps.dataSource;
    delete tagProps.isMobile;
    const animation = {
        y: '+=30',
        opacity: 0,
        type: 'from',
        ease: 'easeOutQuad',
    };
    const videoChildren = dataSource.video.children.video;
    const videoNameArray = videoChildren.split('.');
    const type = videoNameArray[videoNameArray.length - 1];
    return (
        <div {...tagProps} {...dataSource.wrapper}>
            <div {...dataSource.page}>
                <div key="title" {...dataSource.titleWrapper}>
                    {dataSource.titleWrapper.children.map(getChildrenToRender)}
                </div>
                <OverPack {...dataSource.OverPack}>
                    <TweenOne
                        key="video"
                        animation={{...animation, delay: 300}}
                        {...dataSource.video}
                    >
                        {isMobile ? (
                            <video
                                width="100%"
                                loop
                                controls
                                poster={dataSource.video.children.image}
                            >
                                <source src={videoChildren}
                                        type={`video/${type}`}/>
                                <track kind="captions"/>
                            </video>
                        ) : (
                            <VideoPlay
                                loop
                                width="100%"
                                poster={dataSource.video.children.image}
                            >
                                <source src={videoChildren}
                                        type={`video/${type}`}/>
                            </VideoPlay>
                        )}
                    </TweenOne>
                </OverPack>
            </div>
        </div>
    );
}

export default Content4;
